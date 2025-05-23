# -*- coding: utf-8 -*-
"""Pexpect is a Python module for spawning child applications and controlling
them automatically. Pexpect can be used for automating interactive applications
such as ssh, ftp, passwd, telnet, etc. It can be used to a automate setup
scripts for duplicating software package installations on different servers. It
can be used for automated software testing. Pexpect is in the spirit of Don
Libes' Expect, but Pexpect is pure Python. Other Expect-like modules for Python
require TCL and Expect or require C extensions to be compiled. Pexpect does not
use C, Expect, or TCL extensions. It should work on any platform that supports
the standard Python pty module. The Pexpect interface focuses on ease of use so
that simple tasks are easy.

There are two main interfaces to Pexpect -- the function, run() and the class,
spawn. You can call the run() function to execute a command and return the
output. This is a handy replacement for os.system().

For example::

    pexpect.run('ls -la')

The more powerful interface is the spawn class. You can use this to spawn an
external child command and then interact with the child by sending lines and
expecting responses.

For example::

    child = pexpect.spawn('scp foo myname@host.example.com:.')
    child.expect ('Password:')
    child.sendline (mypassword)

This works even for commands that ask for passwords or other input outside of
the normal stdio streams.

Credits: Noah Spurrier, Richard Holden, Marco Molteni, Kimberley Burchett,
Robert Stone, Hartmut Goebel, Chad Schroeder, Erick Tryzelaar, Dave Kirby, Ids
vander Molen, George Todd, Noel Taylor, Nicolas D. Cesar, Alexander Gattin,
Geoffrey Marshall, Francisco Lourenco, Glen Mabey, Karthik Gurusamy, Fernando
Perez, Corey Minyard, Jon Cohen, Guillaume Chazarain, Andrew Ryan, Nick
Craig-Wood, Andrew Stone, Jorgen Grahn (Let me know if I forgot anyone.)

Free, open source, and all that good stuff.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Pexpect Copyright (c) 2008 Noah Spurrier
http://pexpect.sourceforge.net/

$Id: pexpect.py 507 2007-12-27 02:40:52Z noah $
"""

import errno
import os
import re
import select
import signal
import string
import struct
import sys
import time
import traceback

if sys.platform != "win32":
    import pty
    import tty
    import termios
    import resource
    import fcntl
else:
    from io import StringIO
    from ctypes import windll
    import pywintypes
    from win32com.shell.shellcon import CSIDL_APPDATA
    from win32com.shell.shell import SHGetSpecialFolderPath
    from win32console import (
        AllocConsole,
        AttachConsole,
        FreeConsole,
        GetConsoleProcessList,
        GetConsoleWindow,
        GetStdHandle,
        KEY_EVENT,
        PyConsoleScreenBufferType,
        PyCOORDType,
        PyINPUT_RECORDType,
        PySMALL_RECTType,
        SetConsoleOutputCP,
        SetConsoleTitle,
        STD_INPUT_HANDLE,
    )
    from win32process import (
        CreateProcess,
        GetCurrentProcessId,
        GetExitCodeProcess,
        GetStartupInfo,
        GetWindowThreadProcessId,
        ResumeThread,
        SuspendThread,
        TerminateProcess,
    )
    from win32con import (
        CREATE_NEW_CONSOLE,
        CREATE_NEW_PROCESS_GROUP,
        CTRL_BREAK_EVENT,
        FILE_SHARE_READ,
        FILE_SHARE_WRITE,
        GENERIC_READ,
        GENERIC_WRITE,
        OPEN_EXISTING,
        PM_REMOVE,
        PROCESS_QUERY_INFORMATION,
        PROCESS_TERMINATE,
        SW_HIDE,
        SW_SHOW,
        STARTF_USESHOWWINDOW,
        STILL_ACTIVE,
        THREAD_SUSPEND_RESUME,
        WM_USER,
    )
    from win32gui import (
        PeekMessage,
        ShowWindow,
    )
    import win32api
    import win32file
    import winerror


__version__ = "2.3"
__revision__ = "$Revision: 399 $"
__all__ = [
    "ExceptionPexpect",
    "EOF",
    "TIMEOUT",
    "spawn",
    "run",
    "which",
    "split_command_line",
    "__version__",
    "__revision__",
]


from DisplayCAL.meta import name as appname


# Exception classes used by this module.
class ExceptionPexpect(Exception):
    """Base class for all exceptions raised by this module."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    def get_trace(self):
        """This returns an abbreviated stack trace with lines that only concern
        the caller. In other words, the stack trace inside the Pexpect module
        is not included."""

        tblist = traceback.extract_tb(sys.exc_info()[2])
        # tblist = filter(self.__filter_not_pexpect, tblist)
        tblist = [item for item in tblist if self.__filter_not_pexpect(item)]
        tblist = traceback.format_list(tblist)
        return "".join(tblist)

    def __filter_not_pexpect(self, trace_list_item):
        """This returns True if list item 0 the string 'pexpect.py' in it."""

        if trace_list_item[0].find("pexpect.py") == -1:
            return True
        else:
            return False


class EOF(ExceptionPexpect):
    """Raised when EOF is read from a child. This usually means the child has exited."""


class TIMEOUT(ExceptionPexpect):
    """Raised when a read time exceeds the timeout."""


# class TIMEOUT_PATTERN(TIMEOUT):
#     """Raised when the pattern match time exceeds the timeout.
#     This is different than a read TIMEOUT because the child process may
#     give output, thus never give a TIMEOUT, but the output
#     may never match a pattern.
#     """
# class MAXBUFFER(ExceptionPexpect):
#     """Raised when a scan buffer fills before matching an expected pattern."""


def run(
    command,
    timeout=-1,
    withexitstatus=False,
    events=None,
    extra_args=None,
    logfile=None,
    cwd=None,
    env=None,
):
    """This function runs the given command; waits for it to finish; then
    returns all output as a string. STDERR is included in output. If the full
    path to the command is not given then the path is searched.

    Note that lines are terminated by CR/LF (\\r\\n) combination even on
    UNIX-like systems because this is the standard for pseudo ttys. If you set
    'withexitstatus' to true, then run will return a tuple of (command_output,
    exitstatus). If 'withexitstatus' is false then this returns just
    command_output.

    The run() function can often be used instead of creating a spawn instance.
    For example, the following code uses spawn::

        from pexpect import *
        child = spawn('scp foo myname@host.example.com:.')
        child.expect ('(?i)password')
        child.sendline (mypassword)

    The previous code can be replace with the following::

        from pexpect import *
        run ('scp foo myname@host.example.com:.', events={'(?i)password': mypassword})

    Examples
    ========

    Start the apache daemon on the local machine::

        from pexpect import *
        run ("/usr/local/apache/bin/apachectl start")

    Check in a file using SVN::

        from pexpect import *
        run ("svn ci -m 'automatic commit' my_file.py")

    Run a command and capture exit status::

        from pexpect import *
        (command_output, exitstatus) = run ('ls -l /bin', withexitstatus=1)

    Tricky Examples
    ===============

    The following will run SSH and execute 'ls -l' on the remote machine. The
    password 'secret' will be sent if the '(?i)password' pattern is ever seen::

        run ("ssh username@machine.example.com 'ls -l'", events={'(?i)password':'secret\\n'})

    This will start mencoder to rip a video from DVD. This will also display
    progress ticks every 5 seconds as it runs. For example::

        from pexpect import *
        def print_ticks(d):
            print d['event_count'],
        run ("mencoder dvd://1 -o video.avi -oac copy -ovc copy", events={TIMEOUT:print_ticks}, timeout=5)

    The 'events' argument should be a dictionary of patterns and responses.
    Whenever one of the patterns is seen in the command out run() will send the
    associated response string. Note that you should put newlines in your
    string if Enter is necessary. The responses may also contain callback
    functions. Any callback is function that takes a dictionary as an argument.
    The dictionary contains all the locals from the run() function, so you can
    access the child spawn object or any other variable defined in run()
    (event_count, child, and extra_args are the most useful). A callback may
    return True to stop the current run process otherwise run() continues until
    the next event. A callback may also return a string which will be sent to
    the child. 'extra_args' is not used by directly run(). It provides a way to
    pass data to a callback function through run() through the locals
    dictionary passed to a callback."""
    if timeout == -1:
        child = spawn(command, maxread=2000, logfile=logfile, cwd=cwd, env=env)
    else:
        child = spawn(
            command, timeout=timeout, maxread=2000, logfile=logfile, cwd=cwd, env=env
        )
    if events is not None:
        patterns = list(events.keys())
        responses = list(events.values())
    else:
        patterns = None  # We assume that EOF or TIMEOUT will save us.
        responses = None
    child_result_list = []
    event_count = 0
    while 1:
        try:
            index = child.expect(patterns)
            if isinstance(child.after, str):
                child_result_list.append(child.before + child.after)
            else:  # child.after may have been a TIMEOUT or EOF, so don't cat those.
                child_result_list.append(child.before)
            if isinstance(responses[index], str):
                child.send(responses[index])
            elif callable(responses[index]):
                callback_result = responses[index](locals())
                sys.stdout.flush()
                if isinstance(callback_result, str):
                    child.send(callback_result)
                elif callback_result:
                    break
            else:
                raise TypeError("The callback must be a string or function type.")
            event_count = event_count + 1
        except TIMEOUT:
            child_result_list.append(child.before)
            break
        except EOF:
            child_result_list.append(child.before)
            break
    child_result = "".join(child_result_list)
    if withexitstatus:
        child.close()
        return child_result, child.exitstatus
    else:
        return child_result


def spawn(
    command,
    args=None,
    timeout=30,
    maxread=2000,
    searchwindowsize=None,
    logfile=None,
    cwd=None,
    env=None,
    codepage=None,
    columns=None,
    rows=None,
):
    if args is None:
        args = []

    log("=" * 80)
    log(f"Buffer size: {maxread}")
    if searchwindowsize:
        log(f"Search window size: {searchwindowsize}")
    log(f"Timeout: {timeout}s")
    if env:
        log("Environment:")
        for name in env:
            log(f"\t{name}={env[name]}")
    if cwd:
        if isinstance(cwd, bytes):
            cwd = cwd.decode("utf-8")
        log(f"Working directory: {cwd}")
    log("Spawning {}".format(join_args([command] + args)))
    if sys.platform == "win32":
        return spawn_windows(
            command,
            args,
            timeout,
            maxread,
            searchwindowsize,
            logfile,
            cwd,
            env,
            codepage,
            columns,
            rows,
        )
    else:
        return spawn_unix(
            command, args, timeout, maxread, searchwindowsize, logfile, cwd, env
        )


class spawn_unix:
    """The main class interface for Pexpect.

    Use this class to start and control child applications.

    The command parameter may be a string that includes a command and any arguments to
    the command. For example::

        child = pexpect.spawn('/usr/bin/ftp')
        child = pexpect.spawn('/usr/bin/ssh user@example.com')
        child = pexpect.spawn('ls -latr /tmp')

    You may also construct it with a list of arguments like so::

        child = pexpect.spawn('/usr/bin/ftp', [])
        child = pexpect.spawn('/usr/bin/ssh', ['user@example.com'])
        child = pexpect.spawn('ls', ['-latr', '/tmp'])

    After this the child application will be created and will be ready to
    talk to. For normal use, see expect() and send() and sendline().

    Remember that Pexpect does NOT interpret shell meta characters such as
    redirect, pipe, or wild cards (>, |, or *). This is a common mistake.
    If you want to run a command and pipe it through another command then
    you must also start a shell. For example::

        child = pexpect.spawn('/bin/bash -c "ls -l | grep LOG > log_list.txt"')
        child.expect(pexpect.EOF)

    The second form of spawn (where you pass a list of arguments) is useful
    in situations where you wish to spawn a command and pass it its own
    argument list. This can make syntax more clear. For example, the
    following is equivalent to the previous example::

        shell_cmd = 'ls -l | grep LOG > log_list.txt'
        child = pexpect.spawn('/bin/bash', ['-c', shell_cmd])
        child.expect(pexpect.EOF)

    The maxread attribute sets the read buffer size. This is maximum number
    of bytes that Pexpect will try to read from a TTY at one time. Setting
    the maxread size to 1 will turn off buffering. Setting the maxread
    value higher may help performance in cases where large amounts of
    output are read back from the child. This feature is useful in
    conjunction with searchwindowsize.

    The searchwindowsize attribute sets the how far back in the incomming
    seach buffer Pexpect will search for pattern matches. Every time
    Pexpect reads some data from the child it will append the data to the
    incomming buffer. The default is to search from the beginning of the
    imcomming buffer each time new data is read from the child. But this is
    very inefficient if you are running a command that generates a large
    amount of data where you want to match The searchwindowsize does not
    effect the size of the incomming data buffer. You will still have
    access to the full buffer after expect() returns.

    The logfile member turns on or off logging. All input and output will
    be copied to the given file object. Set logfile to None to stop
    logging. This is the default. Set logfile to sys.stdout to echo
    everything to standard output. The logfile is flushed after each write.

    Example log input and output to a file::

        child = pexpect.spawn('some_command')
        fout = file('mylog.txt','w')
        child.logfile = fout

    Example log to stdout::

        child = pexpect.spawn('some_command')
        child.logfile = sys.stdout

    The logfile_read and logfile_send members can be used to separately log
    the input from the child and output sent to the child. Sometimes you
    don't want to see everything you write to the child. You only want to
    log what the child sends back. For example::

        child = pexpect.spawn('some_command')
        child.logfile_read = sys.stdout

    To separately log output sent to the child use logfile_send::

        self.logfile_send = fout

    The delaybeforesend helps overcome a weird behavior that many users
    were experiencing. The typical problem was that a user would expect() a
    "Password:" prompt and then immediately call sendline() to send the
    password. The user would then see that their password was echoed back
    to them. Passwords don't normally echo. The problem is caused by the
    fact that most applications print out the "Password" prompt and then
    turn off stdin echo, but if you send your password before the
    application turned off echo, then you get your password echoed.
    Normally this wouldn't be a problem when interacting with a human at a
    real keyboard. If you introduce a slight delay just before writing then
    this seems to clear up the problem. This was such a common problem for
    many users that I decided that the default pexpect behavior should be
    to sleep just before writing to the child application. 1/20th of a
    second (50 ms) seems to be enough to clear up the problem. You can set
    delaybeforesend to 0 to return to the old behavior. Most Linux machines
    don't like this to be below 0.03. I don't know why.

    Note that spawn is clever about finding commands on your path.
    It uses the same logic that "which" uses to find executables.

    If you wish to get the exit status of the child you must call the
    close() method. The exit or signal status of the child will be stored
    in self.exitstatus or self.signalstatus. If the child exited normally
    then exitstatus will store the exit return code and signalstatus will
    be None. If the child was terminated abnormally with a signal then a
    signalstatus will store the signal value and exitstatus will be None.
    If you need more detail you can also read the self.status member which
    stores the status returned by os.waitpid. You can interpret this using
    os.WIFEXITED/os.WEXITSTATUS or os.WIFSIGNALED/os.TERMSIG.
    """

    def __init__(
        self,
        command,
        args=None,
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        cwd=None,
        env=None,
    ):
        if args is None:
            args = []

        self.STDIN_FILENO = pty.STDIN_FILENO
        self.STDOUT_FILENO = pty.STDOUT_FILENO
        self.STDERR_FILENO = pty.STDERR_FILENO
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

        self.searcher = None
        self.ignorecase = False
        self.before = None
        self.after = None
        self.match = None
        self.match_index = None
        self.terminated = True
        self.exitstatus = None
        self.signalstatus = None
        self.status = None  # status returned by os.waitpid
        self.flag_eof = False
        self.pid = None
        self.child_fd = -1  # initially closed
        self.timeout = timeout
        self.delimiter = EOF
        self.logfile = logfile
        self.logfile_read = None  # input from child (read_nonblocking)
        self.logfile_send = None  # output to send (send, sendline)
        self.maxread = maxread  # max bytes to read at one time into buffer
        self.buffer = ""  # This is the read buffer. See maxread.
        self.searchwindowsize = searchwindowsize  # Anything before searchwindowsize point is preserved, but not searched.
        # Most Linux machines don't like delaybeforesend to be below 0.03 (30 ms).
        self.delaybeforesend = 0.05  # Sets sleep time used just before sending data to child. Time in seconds.
        self.delayafterclose = 0.1  # Sets delay in close() method to allow kernel time to update process status. Time in seconds.
        self.delayafterterminate = 0.1  # Sets delay in terminate() method to allow kernel time to update process status. Time in seconds.
        self.softspace = False  # File-like object.
        self.name = f"<{repr(self)}>"  # File-like object.
        self.encoding = None  # File-like object.
        self.closed = True  # File-like object.
        self.ocwd = os.getcwd()
        self.cwd = cwd
        self.env = env
        self.__irix_hack = (
            sys.platform.lower().find("irix") >= 0
        )  # This flags if we are running on irix
        # Solaris uses internal __fork_pty(). All others use pty.fork().
        if (sys.platform.lower().find("solaris") >= 0) or (
            sys.platform.lower().find("sunos5") >= 0
        ):
            self.use_native_pty_fork = False
        else:
            self.use_native_pty_fork = True

        # allow dummy instances for subclasses that may not use command or args.
        if command is None:
            self.command = None
            self.args = None
            self.name = "<pexpect factory incomplete>"
        else:
            self._spawn(command, args)

    def __del__(self):
        """This makes sure that no system resources are left open. Python only
        garbage collects Python objects. OS file descriptors are not Python
        objects, so they must be handled explicitly. If the child file
        descriptor was opened outside this class (passed to the constructor)
        then this does not close it."""
        if not self.closed:
            # It is possible for __del__ methods to execute during the
            # teardown of the Python VM itself. Thus, self.close() may
            # trigger an exception because os.close may be None.
            # -- Fernando Perez
            try:
                self.close()
            except AttributeError:
                pass

    def __str__(self):
        """This returns a human-readable string that represents the state of
        the object."""
        s = []
        s.append(repr(self))
        s.append("version: " + __version__ + " (" + __revision__ + ")")
        s.append("command: " + str(self.command))
        s.append("args: " + str(self.args))
        s.append("searcher: " + str(self.searcher))
        s.append("buffer (last 100 chars): " + str(self.buffer)[-100:])
        s.append("before (last 100 chars): " + str(self.before)[-100:])
        s.append("after: " + str(self.after))
        s.append("match: " + str(self.match))
        s.append("match_index: " + str(self.match_index))
        s.append("exitstatus: " + str(self.exitstatus))
        s.append("flag_eof: " + str(self.flag_eof))
        s.append("pid: " + str(self.pid))
        s.append("child_fd: " + str(self.child_fd))
        s.append("closed: " + str(self.closed))
        s.append("timeout: " + str(self.timeout))
        s.append("delimiter: " + str(self.delimiter))
        s.append("logfile: " + str(self.logfile))
        s.append("logfile_read: " + str(self.logfile_read))
        s.append("logfile_send: " + str(self.logfile_send))
        s.append("maxread: " + str(self.maxread))
        s.append("ignorecase: " + str(self.ignorecase))
        s.append("searchwindowsize: " + str(self.searchwindowsize))
        s.append("delaybeforesend: " + str(self.delaybeforesend))
        s.append("delayafterclose: " + str(self.delayafterclose))
        s.append("delayafterterminate: " + str(self.delayafterterminate))
        return "\n".join(s)

    def _spawn(self, command, args=None):
        """This starts the given command in a child process. This does all the
        fork/exec type of stuff for a pty. This is called by __init__. If args
        is empty then command will be parsed (split on spaces) and args will be
        set to parsed arguments."""
        if args is None:
            args = []

        # The pid and child_fd of this object get set by this method.
        # Note that it is difficult for this method to fail.
        # You cannot detect if the child process cannot start.
        # So the only way you can tell if the child process started
        # or not is to try to read from the file descriptor. If you get
        # EOF immediately then it means that the child is already dead.
        # That may not necessarily be bad because you may haved spawned a child
        # that performs some task; creates no stdout output; and then dies.

        # If command is an int type then it may represent a file descriptor.
        if isinstance(command, int):
            raise ExceptionPexpect(
                "Command is an int type. If this is a file descriptor then maybe you want to use fdpexpect.fdspawn "
                "which takes an existing file descriptor instead of a command string."
            )

        if not isinstance(args, list):
            raise TypeError("The argument, args, must be a list.")

        if not args:
            self.args = split_command_line(command)
            self.command = self.args[0]
        else:
            self.args = args[:]  # work with a copy
            self.args.insert(0, command)
            self.command = command

        command_with_path = which(self.command)
        if command_with_path is None:
            raise ExceptionPexpect(
                "The command was not found or was not executable: %s." % self.command
            )
        self.command = command_with_path
        self.args[0] = self.command

        new_args = []
        for arg in self.args:
            if isinstance(arg, bytes):
                arg = arg.decode()
            new_args.append(arg)
        self.args = new_args

        self.name = "<" + " ".join(self.args) + ">"

        assert self.pid is None, "The pid member should be None."
        assert self.command is not None, "The command member should not be None."

        if self.use_native_pty_fork:
            try:
                self.pid, self.child_fd = pty.fork()
            except OSError as e:
                raise ExceptionPexpect("Error! pty.fork() failed: " + str(e))
        else:  # Use internal __fork_pty
            self.pid, self.child_fd = self.__fork_pty()

        if self.pid == 0:  # Child
            try:
                self.child_fd = sys.stdout.fileno()  # used by setwinsize()
                self.setwinsize(24, 80)
            except Exception:
                # Some platforms do not like setwinsize (Cygwin).
                # This will cause problem when running applications that
                # are very picky about window size.
                # This is a serious limitation, but not a show stopper.
                pass
            # Do not allow child to inherit open file descriptors from parent.
            max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
            for i in range(3, max_fd):
                try:
                    os.close(i)
                except OSError:
                    pass

            # I don't know why this works, but ignoring SIGHUP fixes a
            # problem when trying to start a Java daemon with sudo
            # (specifically, Tomcat).
            signal.signal(signal.SIGHUP, signal.SIG_IGN)

            if self.cwd is not None:
                os.chdir(self.cwd)
            try:
                if self.env is None:
                    os.execv(self.command, self.args)
                else:
                    os.execvpe(self.command, self.args, self.env)
            finally:
                if self.cwd is not None:
                    # Restore the original working dir
                    os.chdir(self.ocwd)

        # Parent
        self.terminated = False
        self.closed = False

    def __fork_pty(self):
        """This implements a substitute for the forkpty system call. This
        should be more portable than the pty.fork() function. Specifically,
        this should work on Solaris.

        Modified 10.06.05 by Geoff Marshall: Implemented __fork_pty() method to
        resolve the issue with Python's pty.fork() not supporting Solaris,
        particularly ssh. Based on patch to posixmodule.c authored by Noah
        Spurrier::

            http://mail.python.org/pipermail/python-dev/2003-May/035281.html

        """
        parent_fd, child_fd = os.openpty()
        if parent_fd < 0 or child_fd < 0:
            raise ExceptionPexpect("Error! Could not open pty with os.openpty().")

        pid = os.fork()
        if pid < 0:
            raise ExceptionPexpect("Error! Failed os.fork().")
        elif pid == 0:
            # Child.
            os.close(parent_fd)
            self.__pty_make_controlling_tty(child_fd)

            os.dup2(child_fd, 0)
            os.dup2(child_fd, 1)
            os.dup2(child_fd, 2)

            if child_fd > 2:
                os.close(child_fd)
        else:
            # Parent.
            os.close(child_fd)

        return pid, parent_fd

    def __pty_make_controlling_tty(self, tty_fd):
        """This makes the pseudo-terminal the controlling tty. This should be
        more portable than the pty.fork() function. Specifically, this should
        work on Solaris."""
        child_name = os.ttyname(tty_fd)

        # Disconnect from controlling tty if still connected.
        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        if fd >= 0:
            os.close(fd)

        os.setsid()

        # Verify we are disconnected from controlling tty
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
            if fd >= 0:
                os.close(fd)
                raise ExceptionPexpect(
                    "Error! We are not disconnected from a controlling tty."
                )
        except Exception:
            # Good! We are disconnected from a controlling tty.
            pass

        # Verify we can open child pty.
        fd = os.open(child_name, os.O_RDWR)
        if fd < 0:
            raise ExceptionPexpect("Error! Could not open child pty, " + child_name)
        else:
            os.close(fd)

        # Verify we now have a controlling tty.
        fd = os.open("/dev/tty", os.O_WRONLY)
        if fd < 0:
            raise ExceptionPexpect("Error! Could not open controlling tty, /dev/tty")
        else:
            os.close(fd)

    def fileno(self):  # File-like object.
        """This returns the file descriptor of the pty for the child."""
        return self.child_fd

    def close(self, force=True):  # File-like object.
        """This closes the connection with the child application. Note that
        calling close() more than once is valid. This emulates standard Python
        behavior with files. Set force to True if you want to make sure that
        the child is terminated (SIGKILL is sent if the child ignores SIGHUP
        and SIGINT)."""
        if not self.closed:
            self.flush()
            os.close(self.child_fd)
            time.sleep(
                self.delayafterclose
            )  # Give kernel time to update process status.
            if self.isalive():
                if not self.terminate(force):
                    raise ExceptionPexpect(
                        "close() could not terminate the child using terminate()"
                    )
            self.child_fd = -1
            self.closed = True
            # self.pid = None

    def flush(self):  # File-like object.
        """This does nothing. It is here to support the interface for a
        File-like object."""
        pass

    def isatty(self):  # File-like object.
        """This returns True if the file descriptor is open and connected to a
        tty(-like) device, else False."""
        return os.isatty(self.child_fd)

    def waitnoecho(self, timeout=-1):
        """This waits until the terminal ECHO flag is set False. This returns
        True if the echo mode is off. This returns False if the ECHO flag was
        not set False before the timeout. This can be used to detect when the
        child is waiting for a password. Usually a child application will turn
        off echo mode when it is waiting for the user to enter a password. For
        example, instead of expecting the "password:" prompt you can wait for
        the child to set ECHO off::

            p = pexpect.spawn ('ssh user@example.com')
            p.waitnoecho()
            p.sendline(mypassword)

        If timeout is None then this method to block forever until ECHO flag is
        False.

        """
        end_time = -1
        if timeout == -1:
            timeout = self.timeout
        if timeout is not None:
            end_time = time.time() + timeout
        while True:
            if not self.getecho():
                return True
            if timeout < 0 and timeout is not None:
                return False
            if timeout is not None:
                timeout = end_time - time.time()
            time.sleep(0.1)

    def getecho(self):
        """This returns the terminal echo mode. This returns True if echo is
        on or False if echo is off. Child applications that are expecting you
        to enter a password often set ECHO False. See waitnoecho()."""
        attr = termios.tcgetattr(self.child_fd)
        if attr[3] & termios.ECHO:
            return True
        return False

    def setecho(self, state):
        """This sets the terminal echo mode on or off. Note that anything the
        child sent before the echo will be lost, so you should be sure that
        your input buffer is empty before you call setecho(). For example, the
        following will work as expected::

            p = pexpect.spawn('cat')
            p.sendline ('1234') # We will see this twice (once from tty echo and again from cat).
            p.expect (['1234'])
            p.expect (['1234'])
            p.setecho(False) # Turn off tty echo
            p.sendline ('abcd') # We will set this only once (echoed by cat).
            p.sendline ('wxyz') # We will set this only once (echoed by cat)
            p.expect (['abcd'])
            p.expect (['wxyz'])

        The following WILL NOT WORK because the lines sent before the setecho
        will be lost::

            p = pexpect.spawn('cat')
            p.sendline ('1234') # We will see this twice (once from tty echo and again from cat).
            p.setecho(False) # Turn off tty echo
            p.sendline ('abcd') # We will set this only once (echoed by cat).
            p.sendline ('wxyz') # We will set this only once (echoed by cat)
            p.expect (['1234'])
            p.expect (['1234'])
            p.expect (['abcd'])
            p.expect (['wxyz'])
        """
        attr = termios.tcgetattr(self.child_fd)
        if state:
            attr[3] = attr[3] | termios.ECHO
        else:
            attr[3] = attr[3] & ~termios.ECHO
        # I tried TCSADRAIN and TCSAFLUSH, but these were inconsistent
        # and blocked on some platforms. TCSADRAIN is probably ideal if it worked.
        termios.tcsetattr(self.child_fd, termios.TCSANOW, attr)

    def read_nonblocking(self, size=1, timeout=-1):
        """This reads at most size characters from the child application. It
        includes a timeout. If the read does not complete within the timeout
        period then a TIMEOUT exception is raised. If the end of file is read
        then an EOF exception will be raised. If a log file was set using
        setlog() then all data will also be written to the log file.

        If timeout is None then the read may block indefinitely. If timeout is -1
        then the self.timeout value is used. If timeout is 0 then the child is
        polled and if there was no data immediately ready then this will raise
        a TIMEOUT exception.

        The timeout refers only to the amount of time to read at least one
        character. This is not effected by the 'size' parameter, so if you call
        read_nonblocking(size=100, timeout=30) and only one character is
        available right away then one character will be returned immediately.
        It will not wait for 30 seconds for another 99 characters to come in.

        This is a wrapper around os.read(). It uses select.select() to
        implement the timeout."""
        if self.closed:
            raise ValueError("I/O operation on closed file in read_nonblocking().")

        if timeout == -1:
            timeout = self.timeout

        # Note that some systems such as Solaris do not give an EOF when
        # the child dies. In fact, you can still try to read
        # from the child_fd -- it will block forever or until TIMEOUT.
        # For this case, I test isalive() before doing any reading.
        # If isalive() is false, then I pretend that this is the same as EOF.
        if not self.isalive():
            r, w, e = self.__select(
                [self.child_fd], [], [], 0
            )  # timeout of 0 means "poll"
            if not r:
                self.flag_eof = True
                raise EOF(
                    "End Of File (EOF) in read_nonblocking(). Braindead platform."
                )
        elif self.__irix_hack:
            # This is a hack for Irix. It seems that Irix requires a long delay before checking isalive.
            # This adds a 2 second delay, but only when the child is terminated.
            r, w, e = self.__select([self.child_fd], [], [], 2)
            if not r and not self.isalive():
                self.flag_eof = True
                raise EOF("End Of File (EOF) in read_nonblocking(). Pokey platform.")

        r, w, e = self.__select([self.child_fd], [], [], timeout)

        if not r:
            if not self.isalive():
                # Some platforms, such as Irix, will claim that their processes are alive;
                # then timeout on the select; and then finally admit that they are not alive.
                self.flag_eof = True
                raise EOF(
                    "End of File (EOF) in read_nonblocking(). Very pokey platform."
                )
            else:
                raise TIMEOUT("Timeout exceeded in read_nonblocking().")

        if self.child_fd in r:
            try:
                s = os.read(self.child_fd, size)
            except OSError:  # Linux does this
                self.flag_eof = True
                raise EOF(
                    "End Of File (EOF) in read_nonblocking(). Exception style platform."
                )
            if s == b"":  # BSD style
                self.flag_eof = True
                raise EOF(
                    "End Of File (EOF) in read_nonblocking(). Empty string style platform."
                )

            if self.logfile is not None:
                self.logfile.write(s)
                self.logfile.flush()
            if self.logfile_read is not None:
                self.logfile_read.write(s)
                self.logfile_read.flush()

            return s

        raise ExceptionPexpect("Reached an unexpected state in read_nonblocking().")

    def read(self, size=-1):  # File-like object.
        """This reads at most "size" bytes from the file (less if the read hits
        EOF before obtaining size bytes). If the size argument is negative or
        omitted, read all data until EOF is reached. The bytes are returned as
        a string object. An empty string is returned when EOF is encountered
        immediately."""
        if size == 0:
            return ""
        if size < 0:
            self.expect(self.delimiter)  # delimiter default is EOF
            return self.before

        # I could have done this more directly by not using expect(), but
        # I deliberately decided to couple read() to expect() so that
        # I would catch any bugs early and ensure consistant behavior.
        # It's a little less efficient, but there is less for me to
        # worry about if I have to later modify read() or expect().
        # Note, it's OK if size==-1 in the regex. That just means it
        # will never match anything in which case we stop only on EOF.
        cre = re.compile(r".{%d}" % size, re.DOTALL)
        index = self.expect([cre, self.delimiter])  # delimiter default is EOF
        if index == 0:
            return self.after  # self.before should be ''. Should I assert this?
        return self.before

    def readline(self, size=-1):  # File-like object.
        """This reads and returns one entire line. A trailing newline is kept
        in the string, but may be absent when a file ends with an incomplete
        line. Note: This readline() looks for a \\r\\n pair even on UNIX
        because this is what the pseudo tty device returns. So contrary to what
        you may expect you will receive the newline as \\r\\n. An empty string
        is returned when EOF is hit immediately. Currently, the size argument is
        mostly ignored, so this behavior is not standard for a file-like
        object. If size is 0 then an empty string is returned."""
        if size == 0:
            return ""
        index = self.expect(["\r\n", self.delimiter])  # delimiter default is EOF
        if index == 0:
            return self.before + "\r\n"
        else:
            return self.before

    def __iter__(self):  # File-like object.
        """This is to support iterators over a file-like object."""
        return self

    def __next__(self):  # File-like object.
        """This is to support iterators over a file-like object."""
        result = self.readline()
        if result == "":
            raise StopIteration
        return result

    def readlines(self, sizehint=-1):  # File-like object.
        """This reads until EOF using readline() and returns a list containing
        the lines thus read. The optional "sizehint" argument is ignored."""
        lines = []
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    def write(self, s):  # File-like object.
        """This is similar to send() except that there is no return value."""
        self.send(s)

    def writelines(self, sequence):  # File-like object.
        """This call write() for each element in the sequence. The sequence
        can be any iterable object producing strings, typically a list of
        strings. This does not add line separators There is no return value.
        """
        for s in sequence:
            self.write(s)

    def send(self, s):
        """This sends a string to the child process. This returns the number of
        bytes written. If a log file was set then the data is also written to
        the log."""
        time.sleep(self.delaybeforesend)
        if self.logfile is not None:
            self.logfile.write(s)
            self.logfile.flush()
        if self.logfile_send is not None:
            self.logfile_send.write(s)
            self.logfile_send.flush()
        if not isinstance(s, bytes):
            if not isinstance(s, str):
                s = str(s)
            s = s.encode("utf-8")
        c = os.write(self.child_fd, s)
        return c

    def sendline(self, s=""):
        """This is like send(), but it adds a line feed (os.linesep). This
        returns the number of bytes written."""
        n = self.send(s)
        n = n + self.send(os.linesep)
        return n

    def sendcontrol(self, char):
        """This sends a control character to the child such as Ctrl-C or
        Ctrl-D. For example, to send a Ctrl-G (ASCII 7)::

            child.sendcontrol('g')

        See also, sendintr() and sendeof().
        """
        char = char.lower()
        a = ord(char)
        if 97 <= a <= 122:
            a = a - ord("a") + 1
            return self.send(chr(a))
        d = {
            "@": 0,
            "`": 0,
            "[": 27,
            "{": 27,
            "\\": 28,
            "|": 28,
            "]": 29,
            "}": 29,
            "^": 30,
            "~": 30,
            "_": 31,
            "?": 127,
        }
        if char not in d:
            return 0
        return self.send(chr(d[char]))

    def sendeof(self):
        """This sends an EOF to the child. This sends a character which causes
        the pending parent output buffer to be sent to the waiting child
        program without waiting for end-of-line. If it is the first character
        of the line, the read() in the user program returns 0, which signifies
        end-of-file. This means to work as expected a sendeof() has to be
        called at the beginning of a line. This method does not send a newline.
        It is the responsibility of the caller to ensure the eof is sent at the
        beginning of a line."""
        # # Hmmm... how do I send an EOF?
        # #C  if ((m = write(pty, *buf, p - *buf)) < 0)
        # #C      return (errno == EWOULDBLOCK) ? n : -1;
        # fd = sys.stdin.fileno()
        # old = termios.tcgetattr(fd) # remember current state
        # attr = termios.tcgetattr(fd)
        # attr[3] = attr[3] | termios.ICANON # ICANON must be set to recognize EOF
        # try: # use try/finally to ensure state gets restored
        #     termios.tcsetattr(fd, termios.TCSADRAIN, attr)
        #     if hasattr(termios, 'CEOF'):
        #         os.write (self.child_fd, '%c' % termios.CEOF)
        #     else:
        #         # Silly platform does not define CEOF so assume CTRL-D
        #         os.write (self.child_fd, '%c' % 4)
        # finally: # restore state
        #     termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if hasattr(termios, "VEOF"):
            char = termios.tcgetattr(self.child_fd)[6][termios.VEOF]
        else:
            # platform does not define VEOF so assume CTRL-D
            char = chr(4)
        self.send(char)

    def sendintr(self):
        """This sends a SIGINT to the child. It does not require
        the SIGINT to be the first character on a line."""
        if hasattr(termios, "VINTR"):
            char = termios.tcgetattr(self.child_fd)[6][termios.VINTR]
        else:
            # platform does not define VINTR so assume CTRL-C
            char = chr(3)
        self.send(char)

    def eof(self):
        """This returns True if the EOF exception was ever raised."""
        return self.flag_eof

    def terminate(self, force=False):
        """This forces a child process to terminate. It starts nicely with
        SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
        returns True if the child was terminated. This returns False if the
        child could not be terminated."""
        if not self.isalive():
            return True
        try:
            self.kill(signal.SIGHUP)
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            self.kill(signal.SIGCONT)
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            self.kill(signal.SIGINT)
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            if force:
                self.kill(signal.SIGKILL)
                time.sleep(self.delayafterterminate)
                if not self.isalive():
                    return True
                else:
                    return False
            return False
        except OSError:
            # I think there are kernel timing issues that sometimes cause
            # this to happen. I think isalive() reports True, but the
            # process is dead to the kernel.
            # Make one last attempt to see if the kernel is up to date.
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            else:
                return False

    def wait(self):
        """This waits until the child exits. This is a blocking call. This will
        not read any data from the child, so this will block forever if the
        child has unread output and has terminated. In other words, the child
        may have printed output then called exit(); but, technically, the child
        is still alive until its output is read."""
        if self.isalive():
            pid, status = os.waitpid(self.pid, 0)
        else:
            raise ExceptionPexpect("Cannot wait for dead child process.")
        self.exitstatus = os.WEXITSTATUS(status)
        if os.WIFEXITED(status):
            self.status = status
            self.exitstatus = os.WEXITSTATUS(status)
            self.signalstatus = None
            self.terminated = True
        elif os.WIFSIGNALED(status):
            self.status = status
            self.exitstatus = None
            self.signalstatus = os.WTERMSIG(status)
            self.terminated = True
        elif os.WIFSTOPPED(status):
            raise ExceptionPexpect(
                "Wait was called for a child process that is stopped. "
                "This is not supported. Is some other process attempting job "
                "control with our child pid?"
            )
        return self.exitstatus

    def isalive(self):
        """This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exitstatus or signalstatus of the child. This returns True if the child
        process appears to be running or False if not. It can take literally
        SECONDS for Solaris to return the right status."""
        if self.terminated:
            return False

        if self.flag_eof:
            # This is for Linux, which requires the blocking form of waitpid to get
            # status of a defunct process. This is super-lame. The flag_eof would have
            # been set in read_nonblocking(), so this should be safe.
            waitpid_options = 0
        else:
            waitpid_options = os.WNOHANG

        try:
            pid, status = os.waitpid(self.pid, waitpid_options)
        except OSError as e:  # No child processes
            if e.args[0] == str(errno.ECHILD):
                raise ExceptionPexpect(
                    'isalive() encountered condition where "terminated" is 0, '
                    "but there was no child process. "
                    "Did someone else call waitpid() on our process?"
                )
            else:
                raise e

        # I have to do this twice for Solaris. I can't even believe that I figured this out...
        # If waitpid() returns 0 it means that no child process wishes to
        # report, and the value of status is undefined.
        if pid == 0:
            try:
                pid, status = os.waitpid(
                    self.pid, waitpid_options
                )  # os.WNOHANG) # Solaris!
            except OSError as e:  # This should never happen...
                if e.args[0] == str(errno.ECHILD):
                    raise ExceptionPexpect(
                        "isalive() encountered condition that should never happen. "
                        "There was no child process. "
                        "Did someone else call waitpid() on our process?"
                    )
                else:
                    raise e

            # If pid is still 0 after two calls to waitpid() then
            # the process really is alive. This seems to work on all platforms,
            # except for Irix which seems to require a blocking call on waitpid
            # or select, so I let read_nonblocking take care of this situation
            # (unfortunately, this requires waiting through the timeout).
            if pid == 0:
                return True

        if pid == 0:
            return True

        if os.WIFEXITED(status):
            self.status = status
            self.exitstatus = os.WEXITSTATUS(status)
            self.signalstatus = None
            self.terminated = True
        elif os.WIFSIGNALED(status):
            self.status = status
            self.exitstatus = None
            self.signalstatus = os.WTERMSIG(status)
            self.terminated = True
        elif os.WIFSTOPPED(status):
            raise ExceptionPexpect(
                "isalive() encountered condition where child process is "
                "stopped. This is not supported. Is some other process "
                "attempting job control with our child pid?"
            )
        return False

    def kill(self, sig):
        """This sends the given signal to the child application. In keeping
        with UNIX tradition it has a misleading name. It does not necessarily
        kill the child unless you send the right signal."""
        # Same as os.kill, but the pid is given for you.
        if self.isalive():
            os.kill(self.pid, sig)

    def compile_pattern_list(self, patterns):
        """This compiles a pattern-string or a list of pattern-strings.
        Patterns must be a StringType, EOF, TIMEOUT, SRE_Pattern, or a list of
        those. Patterns may also be None which results in an empty list (you
        might do this if waiting for an EOF or TIMEOUT condition without
        expecting any pattern).

        This is used by expect() when calling expect_list(). Thus expect() is
        nothing more than::

             cpl = self.compile_pattern_list(pl)
             return self.expect_list(cpl, timeout)

        If you are using expect() within a loop it may be more
        efficient to compile the patterns first and then call expect_list().
        This avoid calls in a loop to compile_pattern_list()::

             cpl = self.compile_pattern_list(my_pattern)
             while some_condition:
                ...
                i = self.expect_list(clp, timeout)
                ...
        """
        if patterns is None:
            return []
        if not isinstance(patterns, list):
            patterns = [patterns]

        compile_flags = re.DOTALL  # Allow dot to match \n
        if self.ignorecase:
            compile_flags = compile_flags | re.IGNORECASE
        compiled_pattern_list = []
        for p in patterns:
            if isinstance(p, str):
                compiled_pattern_list.append(re.compile(p, compile_flags))
            elif p is EOF:
                compiled_pattern_list.append(EOF)
            elif p is TIMEOUT:
                compiled_pattern_list.append(TIMEOUT)
            elif isinstance(p, re.Pattern):
                compiled_pattern_list.append(p)
            else:
                raise TypeError(
                    "Argument must be one of StringTypes, EOF, TIMEOUT, "
                    f"SRE_Pattern, or a list of those type. {type(p)}"
                )

        return compiled_pattern_list

    def expect(self, pattern, timeout=-1, searchwindowsize=None):
        """Seek through the stream until a pattern is matched.

        The pattern is overloaded and may take several types. The pattern can be a
        StringType, EOF, a compiled re, or a list of any of those types. Strings will be
        compiled to re types.

        This returns the index into the pattern list. If the pattern was not a list this
        returns index 0 on a successful match. This may raise exceptions for EOF or
        TIMEOUT. To avoid the EOF or TIMEOUT exceptions add EOF or TIMEOUT to the
        pattern list. That will cause expect to match an EOF or TIMEOUT condition
        instead of raising an exception.

        If you pass a list of patterns and more than one matches, the first match in the
        stream is chosen. If more than one pattern matches at that point, the leftmost
        in the pattern list is chosen. For example::

            # the input is 'foobar'
            index = p.expect (['bar', 'foo', 'foobar'])
            # returns 1 ('foo') even though 'foobar' is a "better" match

        Please note, however, that buffering can affect this behavior, since input
        arrives in unpredictable chunks. For example::

            # the input is 'foobar'
            index = p.expect (['foobar', 'foo'])
            # returns 0 ('foobar') if all input is available at once,
            # but returs 1 ('foo') if parts of the final 'bar' arrive late

        After a match is found the instance attributes 'before', 'after' and 'match'
        will be set. You can see all the data read before the match in 'before'. You can
        see the data that was matched in 'after'. The re.MatchObject used in the re
        match will be in 'match'. If an error occurred then 'before' will be set to all
        the data read so far and 'after' and 'match' will be None.

        If timeout is -1 then timeout will be set to the self.timeout value.

        A list entry may be EOF or TIMEOUT instead of a string. This will catch these
        exceptions and return the index of the list entry instead of raising the
        exception. The attribute 'after' will be set to the exception type. The
        attribute 'match' will be None. This allows you to write code like this::

                index = p.expect (['good', 'bad', pexpect.EOF, pexpect.TIMEOUT])
                if index == 0:
                    do_something()
                elif index == 1:
                    do_something_else()
                elif index == 2:
                    do_some_other_thing()
                elif index == 3:
                    do_something_completely_different()

        instead of code like this::

                try:
                    index = p.expect (['good', 'bad'])
                    if index == 0:
                        do_something()
                    elif index == 1:
                        do_something_else()
                except EOF:
                    do_some_other_thing()
                except TIMEOUT:
                    do_something_completely_different()

        These two forms are equivalent. It all depends on what you want. You can also
        just expect the EOF if you are waiting for all output of a child to finish. For
        example::

                p = pexpect.spawn('/bin/ls')
                p.expect (pexpect.EOF)
                print p.before

        If you are trying to optimize for speed then see expect_list().
        """
        compiled_pattern_list = self.compile_pattern_list(pattern)
        return self.expect_list(compiled_pattern_list, timeout, searchwindowsize)

    def expect_list(self, pattern_list, timeout=-1, searchwindowsize=-1):
        """Return the index into the pattern_list that matched the child output.

        The list may also contain EOF or TIMEOUT (which are not compiled regular
        expressions). This method is similar to the expect() method except that
        expect_list() does not recompile the pattern list on every call. This may help
        if you are trying to optimize for speed, otherwise just use the expect() method.
        This is called by expect(). If timeout==-1 then the self.timeout value is used.
        If searchwindowsize==-1 then the self.searchwindowsize value is used.
        """
        return self.expect_loop(searcher_re(pattern_list), timeout, searchwindowsize)

    def expect_exact(self, pattern_list, timeout=-1, searchwindowsize=-1):
        """This is similar to expect(), but uses plain string matching instead
        of compiled regular expressions in 'pattern_list'. The 'pattern_list'
        may be a string; a list or other sequence of strings; or TIMEOUT and
        EOF.

        This call might be faster than expect() for two reasons: string
        searching is faster than RE matching, and it is possible to limit the
        search to just the end of the input buffer.

        This method is also useful when you don't want to have to worry about
        escaping regular expression characters that you want to match."""
        if isinstance(pattern_list, str) or pattern_list in (TIMEOUT, EOF):
            pattern_list = [pattern_list]
        return self.expect_loop(
            searcher_string(pattern_list), timeout, searchwindowsize
        )

    def expect_loop(self, searcher, timeout=-1, searchwindowsize=-1):
        """The common loop used inside expect.

        The 'searcher' should be an instance of searcher_re or searcher_string, which
        describes how and what to search for in the input.

        See expect() for other arguments, return value and exceptions.
        """
        self.searcher = searcher

        end_time = -1
        if timeout == -1:
            timeout = self.timeout
        if timeout is not None:
            end_time = time.time() + timeout
        if searchwindowsize == -1:
            searchwindowsize = self.searchwindowsize

        incoming = ""
        try:
            incoming = self.buffer
            freshlen = len(incoming)
            while True:  # Keep reading until exception or return.
                index = searcher.search(incoming, freshlen, searchwindowsize)
                if index >= 0:
                    self.buffer = incoming[searcher.end :]
                    self.before = incoming[: searcher.start]
                    self.after = incoming[searcher.start : searcher.end]
                    self.match = searcher.match
                    self.match_index = index
                    return self.match_index
                # No match at this point
                if timeout < 0 and timeout is not None:
                    raise TIMEOUT("Timeout exceeded in expect_any().")
                # Still have time left, so read more data
                c = self.read_nonblocking(self.maxread, timeout)
                freshlen = len(c)
                time.sleep(0.0001)
                if sys.platform == "win32":
                    incoming += c
                else:
                    incoming += c.decode()
                if timeout is not None:
                    timeout = end_time - time.time()
        except EOF as e:
            self.buffer = ""
            self.before = incoming
            self.after = EOF
            index = searcher.eof_index
            if index >= 0:
                self.match = EOF
                self.match_index = index
                return self.match_index
            else:
                self.match = None
                self.match_index = None
                raise EOF(str(e) + "\n" + str(self))
        except TIMEOUT as e:
            self.buffer = incoming
            self.before = incoming
            self.after = TIMEOUT
            index = searcher.timeout_index
            if index >= 0:
                self.match = TIMEOUT
                self.match_index = index
                return self.match_index
            else:
                self.match = None
                self.match_index = None
                raise TIMEOUT(str(e) + "\n" + str(self))
        except Exception:
            self.before = incoming
            self.after = None
            self.match = None
            self.match_index = None
            raise

    def getwinsize(self):
        """This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols)."""
        TIOCGWINSZ = getattr(termios, "TIOCGWINSZ", 1074295912)
        s = struct.pack("HHHH", 0, 0, 0, 0)
        x = fcntl.ioctl(self.fileno(), TIOCGWINSZ, s)
        return struct.unpack("HHHH", x)[0:2]

    def setwinsize(self, r, c):
        """This sets the terminal window size of the child tty. This will cause
        a SIGWINCH signal to be sent to the child. This does not change the
        physical window size. It changes the size reported to TTY-aware
        applications like vi or curses -- applications that respond to the
        SIGWINCH signal."""
        # Check for buggy platforms. Some Python versions on some platforms
        # (notably OSF1 Alpha and RedHat 7.1) truncate the value for
        # termios.TIOCSWINSZ. It is not clear why this happens.
        # These platforms don't seem to handle the signed int very well;
        # yet other platforms like OpenBSD have a large negative value for
        # TIOCSWINSZ and they don't have a truncate problem.
        # Newer versions of Linux have totally different values for TIOCSWINSZ.
        # Note that this fix is a hack.
        TIOCSWINSZ = getattr(termios, "TIOCSWINSZ", -2146929561)
        if TIOCSWINSZ == 2148037735:  # L is not required in Python >= 2.2.
            TIOCSWINSZ = -2146929561  # Same bits, but with sign.
        # Note, assume ws_xpixel and ws_ypixel are zero.
        s = struct.pack("HHHH", r, c, 0, 0)
        fcntl.ioctl(self.fileno(), TIOCSWINSZ, s)

    def interact(self, escape_character=None, input_filter=None, output_filter=None):
        """This gives control of the child process to the interactive user (the
        human at the keyboard). Keystrokes are sent to the child process, and
        the stdout and stderr output of the child process is printed. This
        simply echos the child stdout and child stderr to the real stdout and
        it echos the real stdin to the child stdin. When the user types the
        escape_character this method will stop. The default for
        escape_character is ^]. This should not be confused with ASCII 27 --
        the ESC character. ASCII 29 was chosen for historical merit because
        this is the character used by 'telnet' as the escape character. The
        escape_character will not be sent to the child process.

        You may pass in optional input and output filter functions. These
        functions should take a string and return a string. The output_filter
        will be passed all the output from the child process. The input_filter
        will be passed all the keyboard input from the user. The input_filter
        is run BEFORE the check for the escape_character.

        Note that if you change the window size of the parent the SIGWINCH
        signal will not be passed through to the child. If you want the child
        window size to change when the parent's window size changes then do
        something like the following example::

            import pexpect, struct, fcntl, termios, signal, sys
            def sigwinch_passthrough (sig, data):
                s = struct.pack("HHHH", 0, 0, 0, 0)
                a = struct.unpack('hhhh', fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ , s))
                global p
                p.setwinsize(a[0],a[1])
            p = pexpect.spawn('/bin/bash') # Note this is global and used in sigwinch_passthrough.
            signal.signal(signal.SIGWINCH, sigwinch_passthrough)
            p.interact()
        """
        if escape_character is None:
            escape_character = chr(29)

        # Flush the buffer.
        self.stdout.write(self.buffer)
        self.stdout.flush()
        self.buffer = ""
        mode = tty.tcgetattr(self.STDIN_FILENO)
        tty.setraw(self.STDIN_FILENO)
        try:
            self.__interact_copy(escape_character, input_filter, output_filter)
        finally:
            tty.tcsetattr(self.STDIN_FILENO, tty.TCSAFLUSH, mode)

    def __interact_writen(self, fd, data):
        """This is used by the ``interact()`` method."""
        if not isinstance(data, bytes):
            data = data.encode("utf-8")
        while data != b"" and self.isalive():
            n = os.write(fd, data)
            data = data[n:]

    def __interact_read(self, fd):
        """This is used by the ``interact()`` method."""
        return os.read(fd, 1000)

    def __interact_copy(
        self, escape_character=None, input_filter=None, output_filter=None
    ):
        """This is used by the ``interact()`` method."""
        while self.isalive():
            r, w, e = self.__select([self.child_fd, self.STDIN_FILENO], [], [])
            if self.child_fd in r:
                try:
                    data = self.__interact_read(self.child_fd)
                except OSError:
                    break
                if output_filter:
                    data = output_filter(data)
                if self.logfile is not None:
                    self.logfile.write(data)
                    self.logfile.flush()
                os.write(self.STDOUT_FILENO, data)
            if self.STDIN_FILENO in r:
                data = self.__interact_read(self.STDIN_FILENO)
                if input_filter:
                    data = input_filter(data)
                i = data.rfind(escape_character)
                if i != -1:
                    data = data[:i]
                    self.__interact_writen(self.child_fd, data)
                    break
                self.__interact_writen(self.child_fd, data)

    def __select(self, iwtd, owtd, ewtd, timeout=None):
        """This is a wrapper around select.select() that ignores signals. If
        select.select raises a select.error exception and errno is an EINTR
        error then it is ignored. Mainly this is used to ignore sigwinch
        (terminal resize)."""
        # if select() is interrupted by a signal (errno==EINTR) then
        # we loop back and enter the select() again.
        end_time = -1
        if timeout is not None:
            end_time = time.time() + timeout
        while True:
            try:
                return select.select(iwtd, owtd, ewtd, timeout)
            except select.error as e:
                if e[0] == errno.EINTR:
                    # if we loop back we have to subtract the amount of time we already waited.
                    if timeout is not None:
                        timeout = end_time - time.time()
                        if timeout < 0:
                            return ([], [], [])
                else:  # something else caused the select.error, so this really is an exception
                    raise

    ##############################################################################
    # The following methods are no longer supported or allowed.

    def setmaxread(self, maxread):
        """This method is no longer supported or allowed. I don't like getters
        and setters without a good reason."""
        raise ExceptionPexpect(
            "This method is no longer supported or allowed. "
            "Just assign a value to the maxread member variable."
        )

    def setlog(self, fileobject):
        """This method is no longer supported or allowed."""
        raise ExceptionPexpect(
            "This method is no longer supported or allowed. "
            "Just assign a value to the logfile member variable."
        )


##############################################################################
# End of spawn_unix class
##############################################################################


class spawn_windows(spawn_unix):
    """This is the main class interface for Pexpect.

    Use this class to start and control child applications.
    """

    def __init__(
        self,
        command,
        args=None,
        timeout=30,
        maxread=60000,
        searchwindowsize=None,
        logfile=None,
        cwd=None,
        env=None,
        codepage=None,
        columns=None,
        rows=None,
    ):
        # super(spawn_windows, self).__init__(
        #     command=command,
        #     args=args,
        #     timeout=timeout,
        #     maxread=maxread,
        #     searchwindowsize=searchwindowsize,
        #     logfile=logfile,
        #     cwd=cwd,
        #     env=env
        # )
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.searcher = None
        self.ignorecase = False
        self.before = None
        self.after = None
        self.match = None
        self.match_index = None
        self.terminated = True
        self.exitstatus = None
        self.signalstatus = None
        self.status = None  # status returned by os.waitpid
        self.flag_eof = False
        self.pid = None
        self.child_fd = -1  # initially closed
        self.timeout = timeout
        self.delimiter = EOF
        self.logfile = logfile
        self.logfile_read = None  # input from child (read_nonblocking)
        self.logfile_send = None  # output to send (send, sendline)
        self.maxread = maxread  # max bytes to read at one time into buffer
        self.buffer = ""  # This is the read buffer. See maxread.
        self.searchwindowsize = searchwindowsize  # Anything before searchwindowsize point is preserved, but not searched.
        self.delaybeforesend = 0.05  # Sets sleep time used just before sending data to child. Time in seconds.
        self.delayafterclose = 0.1  # Sets delay in close() method to allow kernel time to update process status. Time in seconds.
        self.delayafterterminate = 0.1  # Sets delay in terminate() method to allow kernel time to update process status. Time in seconds.
        self.softspace = False  # File-like object.
        self.name = f"<{repr(self)}>"  # File-like object.
        self.encoding = None  # File-like object.
        self.closed = True  # File-like object.
        self.ocwd = os.getcwd()
        self.cwd = cwd
        self.env = env
        self.codepage = codepage
        self.columns = columns
        self.rows = rows
        self.wtty = None

        if args is None:
            args = []

        # if any of the args contain any spaces (most possibly a path),
        # we need to quote them
        for i, arg in enumerate(args):
            if " " in arg:
                log("Quoting argument {}: {}".format(i, arg))
                args[i] = '"{}"'.format(arg)

        # allow dummy instances for subclasses that may not use command or args.
        if command is None:
            self.command = None
            self.args = None
            self.name = "<pexpect factory incomplete>"
        else:
            self._spawn(command, args)

    def __del__(self):
        """Make sure that no system resources are left open.

        Python only garbage collects Python objects, not the child console.
        """
        try:
            self.wtty.terminate_child()
        except Exception:
            pass
        try:
            self.wtty.terminate()
        except Exception:
            pass

    def _spawn(self, command, args=None):
        """Start the given command in a child process.

        This does all the fork/exec type of stuff for a pty. This is called by
        __init__. If args is empty then command will be parsed (split on
        spaces) and args will be set to parsed arguments.
        """
        if args is None:
            args = []

        # The pid and child_fd of this object get set by this method.
        # Note that it is difficult for this method to fail.
        # You cannot detect if the child process cannot start.
        # So the only way you can tell if the child process started
        # or not is to try to read from the file descriptor. If you get
        # EOF immediately then it means that the child is already dead.
        # That may not necessarily be bad because you may haved spawned a child
        # that performs some task; creates no stdout output; and then dies.

        # If command is an int type then it may represent a file descriptor.
        if isinstance(command, int):
            raise ExceptionPexpect(
                "Command is an int type. If this is a file descriptor then"
                "maybe you want to use fdpexpect.fdspawn which takes an "
                "existing file descriptor instead of a command string."
            )

        if not isinstance(args, list):
            raise TypeError("The argument, args, must be a list.")

        if not args:
            # Momentairly broken - path '\' characters being misinterpreted
            # self.args = split_command_line(command)
            self.args = [command]
            self.command = self.args[0]
        else:
            self.args = args[:]  # work with a copy
            self.args.insert(0, command)
            self.command = command

        command_with_path = which(self.command)
        if command_with_path is None:
            raise ExceptionPexpect(
                f"The command was not found or was not executable: {self.command}."
            )
        self.command = command_with_path
        self.args[0] = self.command

        self.name = f"<{' '.join(self.args)}>"

        # assert self.pid is None, 'The pid member should be None.'
        # assert self.command is not None, 'The command member should not be None.'

        self.wtty = Wtty(
            timeout=self.timeout,
            codepage=self.codepage,
            columns=self.columns,
            rows=self.rows,
            cwd=self.cwd,
        )

        self.child_fd = self.wtty.spawn(self.command, self.args, self.env)

        self.terminated = False
        self.closed = False
        self.pid = self.wtty.pid

    def fileno(self):  # File-like object.
        """There is no child fd."""
        return 0

    def close(self, force=True):  # File-like object.
        """Closes the child console."""
        self.closed = self.terminate(force)
        if not self.closed:
            raise ExceptionPexpect(
                "close() could not terminate the child using terminate()"
            )
        self.closed = True

    def isatty(self):  # File-like object.
        """The child is always created with a console."""
        return True

    def getecho(self):
        """This returns the terminal echo mode. This returns True if echo is
        on or False if echo is off. Child applications that are expecting you
        to enter a password often set ECHO False. See waitnoecho()."""
        return self.wtty.getecho()

    def setecho(self, state):
        """This sets the terminal echo mode on or off."""
        self.wtty.setecho(state)

    def read_nonblocking(self, size=1, timeout=-1):
        """This reads at most size characters from the child application. It
        includes a timeout. If the read does not complete within the timeout
        period then a TIMEOUT exception is raised. If the end of file is read
        then an EOF exception will be raised. If a log file was set using
        setlog() then all data will also be written to the log file.

        If timeout is None then the read may block indefinitely. If timeout is -1
        then the self.timeout value is used. If timeout is 0 then the child is
        polled and if there was no data immediately ready then this will raise
        a TIMEOUT exception.

        The timeout refers only to the amount of time to read at least one
        character. This is not effected by the 'size' parameter, so if you call
        read_nonblocking(size=100, timeout=30) and only one character is
        available right away then one character will be returned immediately.
        It will not wait for 30 seconds for another 99 characters to come in.

        This is a wrapper around Wtty.read().
        """
        if self.closed:
            raise ValueError("I/O operation on closed file in read_nonblocking().")

        if timeout == -1:
            timeout = self.timeout

        s = self.wtty.read_nonblocking(timeout, size)
        if s == "":
            if not self.wtty.isalive():
                self.flag_eof = True
                raise EOF("End Of File (EOF) in read_nonblocking().")
            if timeout is None:
                # Do not raise TIMEOUT because we might be waiting for EOF
                # sleep to keep CPU utilization down
                time.sleep(0.05)
            else:
                raise TIMEOUT("Timeout exceeded in read_nonblocking().")
        else:
            if self.logfile is not None:
                self.logfile.write(s)
                self.logfile.flush()
            if self.logfile_read is not None:
                self.logfile_read.write(s)
                self.logfile_read.flush()

        return s

    def send(self, s):
        """This sends a string to the child process. This returns the number of
        bytes written. If a log file was set then the data is also written to
        the log."""
        (self.delaybeforesend)
        if self.logfile is not None:
            self.logfile.write(s)
            self.logfile.flush()
        if self.logfile_send is not None:
            self.logfile_send.write(s)
            self.logfile_send.flush()
        c = self.wtty.write(s)
        return c

    # UNIMPLEMENTED ###
    def sendcontrol(self, char):
        raise ExceptionPexpect("sendcontrol() is not supported on windows")

    # UNIMPLEMENTED ###
    # Parent buffer does not wait for endline by default.
    def sendeof(self):
        raise ExceptionPexpect("sendeof() is not supported on windows")

    def sendintr(self):
        """This sends a SIGINT to the child. It does not require
        the SIGINT to be the first character on a line."""
        self.wtty.sendintr()

    def terminate(self, force=False):
        """Terminate the child. Force not used."""
        if not self.isalive():
            return True

        self.wtty.terminate_child()
        time.sleep(self.delayafterterminate)
        if not self.isalive():
            return True

        return False

    def kill(self, sig):
        """Sig == sigint for ctrl-c otherwise the child is terminated."""
        if sig == signal.SIGINT:
            self.wtty.sendintr()
        else:
            self.wtty.terminate_child()

    def wait(self):
        """This waits until the child exits. This is a blocking call. This will
        not read any data from the child, so this will block forever if the
        child has unread output and has terminated. In other words, the child
        may have printed output then called exit(); but, technically, the child
        is still alive until its output is read.
        """
        if not self.isalive():
            raise ExceptionPexpect("Cannot wait for dead child process.")

        # We can't use os.waitpid under Windows because of 'permission denied'
        # exception? Perhaps if not running as admin (or UAC enabled under
        # Vista/7). Simply loop and wait for child to exit.
        while self.isalive():
            time.sleep(0.05)  # Keep CPU utilization down

        return self.exitstatus

    def isalive(self):
        """Determines if the child is still alive."""
        if self.terminated:
            return False

        if self.wtty.isalive():
            return True
        else:
            self.exitstatus = GetExitCodeProcess(self.wtty.getchild())
            # left-shift exit status by 8 bits like os.waitpid
            self.status = self.exitstatus << 8
            self.terminated = True
            return False

    def getwinsize(self):
        """This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols).
        """
        return self.wtty.getwinsize()

    def setwinsize(self, r, c):
        """Set the size of the child screen buffer."""
        self.wtty.setwinsize(r, c)

    # Prototype changed
    def interact(self, escape_character=chr(29), input_filter=None, output_filter=None):
        """Makes the child console visible for interaction"""
        self.wtty.interact()

    # Prototype changed
    def stop_interact(self):
        """Hides the child console from the user."""
        self.wtty.stop_interact()


class Wtty:
    """"""

    def __init__(self, timeout=30, codepage=None, columns=None, rows=None, cwd=None):
        self.__buffer = StringIO()
        self.__bufferY = 0
        self.__currentReadCo = PyCOORDType(0, 0)
        self.__parentPid = 0
        self.__oproc = 0
        self.conpid = 0
        self.__otid = 0
        self.__switch = True
        self.__childProcess = None
        self.codepage = (
            codepage
            or windll.kernel32.GetConsoleOutputCP()
            or windll.kernel32.GetOEMCP()
        )
        log(f"Code page: {self.codepage}")
        log(f"hasattr(sys, 'frozen'): {hasattr(sys, 'frozen')}")
        if getattr(sys, "frozen", False):
            log(f"sys.frozen            : {sys.frozen}")
            log(f"type(sys.frozen)      : {type(sys.frozen)}")
        self.columns = columns
        if isinstance(cwd, bytes):
            cwd = cwd.decode("utf-8")
        self.cwd = cwd
        self.rows = rows
        self.console = False
        self.lastRead = 0
        self.lastReadData = ""
        self.pid = None
        self.processList = []
        # We need a timeout for connecting to the child process
        self.timeout = timeout
        self.totalRead = 0

    def spawn(self, command, args=None, env=None):
        """Spawns spawner.py with correct arguments."""
        if args is None:
            args = []

        ts = time.time()
        self.startChild(args, env)

        while True:
            msg = PeekMessage(0, 0, 0, PM_REMOVE)
            childPid = msg[1][2]
            # Sometimes GetMessage returns a bogus PID, so keep calling it
            # until we can successfully connect to the child or timeout is
            # reached
            if childPid:
                try:
                    self.__childProcess = win32api.OpenProcess(
                        PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION, False, childPid
                    )
                except pywintypes.error:
                    pass
                else:
                    self.pid = childPid
                    break
            if time.time() > ts + self.timeout:
                log("Timeout exceeded in Wtty.spawn().")
                break
            time.sleep(0.05)

        if not self.__childProcess:
            raise ExceptionPexpect(f"The process {args[0]} could not be started.")

        winHandle = int(GetConsoleWindow())
        self.__switch = True
        if winHandle != 0:
            self.__parentPid = GetWindowThreadProcessId(winHandle)[1]
            # Do we have a console attached? Do not rely on winHandle, because
            # it will also be non-zero if we didn't have a console, and then
            # spawned a child process! Using sys.stdout.isatty() seems safe
            self.console = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
            # If the original process had a console, record a list of attached
            # processes so we can check if we need to reattach/reallocate the
            # console later
            self.processList = GetConsoleProcessList()
        else:
            self.switchTo(False)
            self.__switch = False

    def startChild(self, args, env):
        si = GetStartupInfo()
        si.dwFlags = STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE
        # Determine the directory of wexpect.py or, if we are running 'frozen'
        # (eg. py2exe deployment), of the packed executable
        dirname = os.path.dirname(
            sys.executable
            if getattr(sys, "frozen", False)
            else os.path.abspath(os.path.dirname(__file__))
        )
        if getattr(sys, "frozen", False):
            logdir = appname
        else:
            logdir = dirname
        logdir = os.path.basename(logdir)
        spath = [dirname]
        pyargs = ["-c"]
        if getattr(sys, "frozen", False):
            # If we are running 'frozen', add library.zip and lib\library.zip
            # to sys.path
            # py2exe: Needs appropriate 'zipfile' option in setup script and
            # 'bundle_files' 3
            spath.append(os.path.join(dirname, "library.zip"))
            spath.append(os.path.join(dirname, "library.zip", appname))
            if os.path.isdir(os.path.join(dirname, "lib")):
                dirname = os.path.join(dirname, "lib")
                spath.append(os.path.join(dirname, "library.zip"))
                spath.append(os.path.join(dirname, "library.zip", appname))
            # DEBUG: add lib/temp dir for debugging ArgyllCMS executables not starting problem
            spath.append(os.path.join(dirname, "temp"))

            pyargs.insert(0, "-S")  # skip 'import site'
        pid = GetCurrentProcessId()
        tid = win32api.GetCurrentThreadId()
        # If we are running 'frozen', expect python.exe in the same directory
        # as the packed executable.
        # py2exe: The python executable can be included via setup script by
        # adding it to 'data_files'
        command_line = '"{}" {} "{}"'.format(
            (
                os.path.join(dirname, "python.exe")
                if getattr(sys, "frozen", False)
                else os.path.join(os.path.dirname(sys.executable), "python.exe")
            ),
            " ".join(pyargs),
            "import sys;{}sys.path = {} + sys.path;"
            "args = {}; from DisplayCAL import wexpect;"
            "wexpect.ConsoleReader("
            "wexpect.join_args(args), {:d}, {:d}, cp={}, c={}, r={}, logdir={}"
            ")".format(
                # this fixes running Argyll commands through py2exe frozen python
                (
                    "setattr(sys, 'frozen', '{}'); ".format(getattr(sys, "frozen"))
                    if hasattr(sys, "frozen")
                    else ""
                ),
                ("{}".format(repr(spath))).replace('"', r"\""),
                ("{}".format(repr(args))).replace('"', r"\""),
                pid,
                tid,
                self.codepage,
                self.columns,
                self.rows,
                repr(logdir),
            ),
        )

        log(f"command_line: {command_line}")

        if getattr(sys, "frozen", False):
            # without the PYTHONHOME and PYTHONPATH the executable will not run
            # with the frozen python interpreter
            env["PYTHONHOME"] = dirname
            env["PYTHONPATH"] = os.pathsep.join(spath)

        log(f"env: {env}")

        self.__oproc, _, self.conpid, self.__otid = CreateProcess(
            None, command_line, None, None, False, CREATE_NEW_CONSOLE, env, self.cwd, si
        )

    def switchTo(self, attached=True):
        """Release from the current console and attatches to the childs."""
        if not self.__switch or not self.__oproc_isalive():
            return

        if attached:
            FreeConsole()

        AttachConsole(self.conpid)
        self.__consin = GetStdHandle(STD_INPUT_HANDLE)
        self.__consout = self.getConsoleOut()

    def switchBack(self):
        """Releases from the current console and attaches
        to the parents."""
        if not self.__switch or not self.__oproc_isalive():
            return

        if self.console:
            # If we originally had a console, re-attach it (or allocate a new one)
            # If we didn't have a console to begin with, there's no need to
            # re-attach/allocate
            FreeConsole()
            if len(self.processList) > 1:
                # Our original console is still present, re-attach
                AttachConsole(self.__parentPid)
            else:
                # Our original console has been free'd, allocate a new one
                AllocConsole()

        self.__consin = None
        self.__consout = None

    def getConsoleOut(self):
        consout = win32file.CreateFile(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            0,
        )
        return PyConsoleScreenBufferType(consout)

    def getchild(self):
        """Returns a handle to the child process."""
        return self.__childProcess

    def terminate(self):
        """Terminate the ConsoleReader process."""
        win32api.TerminateProcess(self.__oproc, 1)

    def terminate_child(self):
        """Terminate the child process."""
        win32api.TerminateProcess(self.__childProcess, 1)

    def createKeyEvent(self, char):
        """Creates a single key record corresponding to
        the ascii character char."""
        evt = PyINPUT_RECORDType(KEY_EVENT)
        evt.KeyDown = True
        evt.Char = char
        if char in ("\n", "\r"):
            evt.VirtualKeyCode = 0x0D  # VK_RETURN
        evt.RepeatCount = 1
        return evt

    def write(self, s):
        """Writes input into the child consoles input buffer."""
        if len(s) == 0:
            return 0
        records = [self.createKeyEvent(c) for c in str(s)]
        self.switchTo()
        try:
            wrote = self.__consin.WriteConsoleInput(records)
        except Exception as e:
            log(e, "_exceptions")
            self.switchBack()
            raise
        self.switchBack()
        return wrote

    def getPoint(self, offset):
        """Converts an offset to a point represented as a tuple."""
        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        x = offset % consinfo["Size"].X
        y = offset / consinfo["Size"].X
        return x, y

    def getOffset(self, x, y):
        """Converts a tuple-point to an offset."""
        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        return x + y * consinfo["Size"].X

    def readConsole(self, startCo, endCo):
        """Reads the console area from startCo to endCo and returns it as a string."""
        buff = []
        self.lastRead = 0

        startCo = PyCOORDType(startCo.X, startCo.Y)
        endX = endCo.X
        endY = endCo.Y

        while True:
            startOff = self.getOffset(startCo.X, startCo.Y)
            endOff = self.getOffset(endX, endY)
            readlen = endOff - startOff

            if readlen > 4000:
                readlen = 4000
                endPoint = self.getPoint(startOff + 4000)
            else:
                endPoint = self.getPoint(endOff)

            s = self.__consout.ReadConsoleOutputCharacter(readlen, startCo)
            ln = len(s)
            self.lastRead += ln
            self.totalRead += ln
            buff.append(s)

            startCo.X, startCo.Y = int(endPoint[0]), int(endPoint[1])
            if readlen <= 0 or (startCo.X >= endX and startCo.Y >= endY):
                break

        return "".join(buff)

    def parseData(self, s):
        """Ensures that special characters are interpreted as
        newlines or blanks, depending on if there written over
        characters or screen-buffer-fill characters."""
        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        strlist = []
        for i, c in enumerate(s):
            strlist.append(c)
            if (self.totalRead - self.lastRead + i + 1) % consinfo["Size"].X == 0:
                strlist.append("\r\n")

        s = "\r\n".join([line.rstrip(" ") for line in "".join(strlist).split("\r\n")])
        try:
            return s  # .encode("cp%i" % self.codepage, "replace")
        except LookupError:
            return s  # .encode(
            #    getattr(sys.stdout, "encoding", None) or sys.getdefaultencoding(),
            #    "replace",
            # )

    def readConsoleToCursor(self):
        """Reads from the current read position to the current cursor
        position and inserts the string into self.__buffer.
        """
        if not self.__consout:
            return ""

        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        cursorPos = consinfo["CursorPosition"]

        # log('=' * 80)
        # log('cursor: %r, current: %r' % (cursorPos, self.__currentReadCo))

        if cursorPos.Y < self.__currentReadCo.Y:
            # Has the child cleared the screen buffer?
            self.__buffer.seek(0)
            self.__buffer.truncate()
            self.__bufferY = 0
            self.__currentReadCo.X = 0
            self.__currentReadCo.Y = 0

        isSameX = cursorPos.X == self.__currentReadCo.X
        isSameY = cursorPos.Y == self.__currentReadCo.Y
        isSamePos = isSameX and isSameY

        # log('isSameY: %r' % isSameY)
        # log('isSamePos: %r' % isSamePos)

        if isSameY or not self.lastReadData.endswith("\r\n"):
            # Read the current slice again
            self.totalRead -= self.lastRead
            self.__currentReadCo.X = 0
            self.__currentReadCo.Y = self.__bufferY

        # log('cursor: %r, current: %r' % (cursorPos, self.__currentReadCo))

        raw = self.readConsole(self.__currentReadCo, cursorPos)
        rawlist = []
        while raw:
            rawlist.append(raw[: consinfo["Size"].X])
            raw = raw[consinfo["Size"].X :]
        raw = "".join(rawlist)
        s = self.parseData(raw)
        for i, line in enumerate(reversed(rawlist)):
            if len(line) == consinfo["Size"].X:
                # Record the Y offset where the most recent line break was detected
                self.__bufferY += len(rawlist) - i
                break

        # log('lastReadData: %r' % self.lastReadData)
        # log('s: %r' % s)

        # isSameData = False
        if isSamePos and self.lastReadData == s:
            # isSameData = True
            s = ""

        # log('isSameData: %r' % isSameData)
        # log('s: %r' % s)
        if s:
            lastReadData = self.lastReadData
            pos = self.getOffset(self.__currentReadCo.X, self.__currentReadCo.Y)
            self.lastReadData = s
            if isSameY or not lastReadData.endswith("\r\n"):
                # Detect changed lines
                self.__buffer.seek(pos)
                buf = self.__buffer.read()
                # log('buf: %r' % buf)
                # log('raw: %r' % raw)
                if raw.startswith(buf):
                    # Line has grown
                    rawslice = raw[len(buf) :]
                    # Update last read bytes so line breaks can be detected in parseData
                    lastRead = self.lastRead
                    self.lastRead = len(rawslice)
                    s = self.parseData(rawslice)
                    self.lastRead = lastRead
                else:
                    # Cursor has been repositioned
                    s = "\r" + s
                # log('s:   %r' % s)
            self.__buffer.seek(pos)
            self.__buffer.truncate()
            self.__buffer.write(raw)

        self.__currentReadCo.X = cursorPos.X
        self.__currentReadCo.Y = cursorPos.Y

        return s

    def read_nonblocking(self, timeout, size):
        """Reads data from the console if available, otherwise
        waits timeout seconds, and writes the string 'None'
        to the pipe if no data is available after that time.
        """
        self.switchTo()

        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        cursorPos = consinfo["CursorPosition"]
        maxconsoleY = consinfo["Size"].Y / 2
        reset = False
        eof = False
        try:
            while True:
                # Wait for child process to be paused
                if cursorPos.Y > maxconsoleY:
                    reset = True
                    time.sleep(0.2)

                start = time.time()
                s = self.readConsoleToCursor()

                if reset:
                    self.refreshConsole()
                    reset = False

                if len(s) != 0:
                    self.switchBack()
                    return s

                if eof or timeout <= 0:
                    self.switchBack()
                    if eof and self.__oproc_isalive():
                        try:
                            TerminateProcess(self.__oproc, 0)
                        except pywintypes.error as e:
                            log(e, "_exceptions")
                            log("Could not terminate ConsoleReader after child exited.")
                    return ""

                if not self.isalive():
                    eof = True
                    # Child has already terminated, but there may still be
                    # output coming in with a slight delay
                    time.sleep(0.1)

                time.sleep(0.001)
                end = time.time()
                timeout -= end - start

        except Exception as e:
            log(e, "_exceptions")
            log("End Of File (EOF) in Wtty.read_nonblocking().")
            self.switchBack()
            raise EOF("End Of File (EOF) in Wtty.read_nonblocking().")

    def refreshConsole(self):
        """Clears the console after pausing the child and
        reading all the data currently on the console.
        The last line before clearing becomes the first line after clearing."""
        consinfo = self.__consout.GetConsoleScreenBufferInfo()
        cursorPos = consinfo["CursorPosition"]
        startCo = PyCOORDType(0, cursorPos.Y)
        self.totalRead = 0
        raw = self.readConsole(startCo, cursorPos)
        orig = PyCOORDType(0, 0)
        self.__consout.SetConsoleCursorPosition(orig)
        writelen = consinfo["Size"].X * consinfo["Size"].Y
        self.__consout.FillConsoleOutputCharacter(" ", writelen, orig)
        self.__consout.WriteConsoleOutputCharacter(raw, orig)
        cursorPos.Y = 0
        self.__consout.SetConsoleCursorPosition(cursorPos)
        self.__currentReadCo = cursorPos

        self.__bufferY = 0
        self.__buffer.truncate(0)
        self.__buffer.write(raw)

    def setecho(self, state):
        """Sets the echo mode of the child console."""
        self.switchTo()
        try:
            mode = self.__consin.GetConsoleMode()
            if state:
                mode |= 0x0004
            else:
                mode &= ~0x0004
            self.__consin.SetConsoleMode(mode)
        except BaseException:
            self.switchBack()
            raise
        self.switchBack()

    def getecho(self):
        """Returns the echo mode of the child console."""
        self.switchTo()
        try:
            mode = self.__consin.GetConsoleMode()
            ret = (mode & 0x0004) > 0
            self.switchBack()
        except BaseException:
            self.switchBack()
            raise
        return ret

    def getwinsize(self):
        """Returns the size of the child console as a tuple of
        (rows, columns)."""
        self.switchTo()
        try:
            size = self.__consout.GetConsoleScreenBufferInfo()["Size"]
            self.switchBack()
        except BaseException:
            self.switchBack()
            raise
        return (size.Y, size.X)

    def setwinsize(self, r, c):
        """Sets the child console screen buffer size to (r, c)."""
        self.switchTo()
        try:
            self.__consout.SetConsoleScreenBufferSize(PyCOORDType(c, r))
        except Exception:
            self.switchBack()
            raise
        self.switchBack()

    def interact(self):
        """Displays the child console for interaction."""
        if not self.isalive():
            return

        self.switchTo()
        try:
            ShowWindow(GetConsoleWindow(), SW_SHOW)
        except Exception:
            self.switchBack()
            raise
        self.switchBack()

    def stop_interact(self):
        """Hides the child console."""
        self.switchTo()
        try:
            ShowWindow(GetConsoleWindow(), SW_HIDE)
        except Exception:
            self.switchBack()
            raise
        self.switchBack()

    def isalive(self):
        """True if the child is still alive, false otherwise"""
        return GetExitCodeProcess(self.__childProcess) == STILL_ACTIVE

    def __oproc_isalive(self):
        return GetExitCodeProcess(self.__oproc) == STILL_ACTIVE

    def sendintr(self):
        """Sends the sigint signal to the child."""
        self.switchTo()
        try:
            time.sleep(0.15)
            win32api.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, self.pid)
            time.sleep(0.25)
        except Exception:
            self.switchBack()
            raise
        self.switchBack()


class ConsoleReader:
    def __init__(self, path, pid, tid, env=None, cp=None, c=None, r=None, logdir=None):
        self.logdir = logdir
        log("=" * 80, "consolereader", logdir)
        log(f"OEM code page: {windll.kernel32.GetOEMCP()}", "consolereader", logdir)
        consolecp = windll.kernel32.GetConsoleOutputCP()
        log(f"Console output code page: {consolecp}", "consolereader", logdir)
        if consolecp != cp:
            log(f"Setting console output code page to {cp}", "consolereader", logdir)
            try:
                SetConsoleOutputCP(cp)
            except Exception as e:
                log(e, "consolereader_exceptions", logdir)
            else:
                log(
                    f"Console output code page: {windll.kernel32.GetConsoleOutputCP()}",
                    "consolereader",
                    logdir,
                )
        log(f"Spawning {path}", "consolereader", logdir)
        try:
            try:
                consout = self.getConsoleOut()
                self.initConsole(consout, c, r)
                SetConsoleTitle(path)

                si = GetStartupInfo()
                # We do not actually need stdio inherited - Wtty reads from the console.
                # Python 3.x sets STARTF_USESTDHANDLES flag but the stdio handles do not
                # correspond to console.
                # That causes Argyll to not write anything to console for us.
                si.dwFlags = STARTF_USESHOWWINDOW
                si.wShowWindow = SW_HIDE
                # si.wShowWindow = SW_SHOW
                self.__childProcess, _, childPid, self.__tid = CreateProcess(
                    None,
                    path,
                    None,
                    None,
                    False,
                    # The console has been created in the script that launches this
                    # class, and reconfigured from here.
                    CREATE_NEW_PROCESS_GROUP,
                    None,
                    None,
                    si,
                )
            except Exception as e:
                log(e, "consolereader_exceptions", logdir)
                time.sleep(0.1)
                win32api.PostThreadMessage(int(tid), WM_USER, 0, 0)
                sys.exit()

            time.sleep(0.1)

            win32api.PostThreadMessage(int(tid), WM_USER, childPid, 0)

            parent = win32api.OpenProcess(
                PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION, 0, int(pid)
            )
            paused = False

            cursorinfo = consout.GetConsoleCursorInfo()

            while GetExitCodeProcess(self.__childProcess) == STILL_ACTIVE:
                try:
                    if GetExitCodeProcess(parent) != STILL_ACTIVE:
                        try:
                            TerminateProcess(self.__childProcess, 0)
                        except pywintypes.error as e:
                            log(e, "consolereader_exceptions", logdir)
                        sys.exit()

                    consinfo = consout.GetConsoleScreenBufferInfo()
                    cursorPos = consinfo["CursorPosition"]
                    maxconsoleY = consinfo["Size"].Y / 2

                    if cursorPos.Y > maxconsoleY and not paused:
                        # log('ConsoleReader.__init__: cursorPos %s' % cursorPos, 'consolereader', logdir)
                        # log('suspendThread', 'consolereader', logdir)
                        self.suspendThread()
                        paused = True
                        SetConsoleTitle(f"{path} (suspended)")
                        # Hide cursor
                        consout.SetConsoleCursorInfo(cursorinfo[0], 0)

                    if cursorPos.Y <= maxconsoleY and paused:
                        # log('ConsoleReader.__init__: cursorPos %s' % cursorPos, 'consolereader', logdir)
                        # log('resumeThread', 'consolereader', logdir)
                        self.resumeThread()
                        paused = False
                        SetConsoleTitle(path)
                        # Show cursor
                        consout.SetConsoleCursorInfo(cursorinfo[0], cursorinfo[1])

                    time.sleep(0.1)
                except KeyboardInterrupt:
                    # Only let child react to CTRL+C, ignore in ConsoleReader
                    pass

            SetConsoleTitle(f"ConsoleReader: {path} (terminated)")
            consout.SetConsoleCursorInfo(cursorinfo[0], 0)  # Hide cursor

            while GetExitCodeProcess(parent) == STILL_ACTIVE:
                time.sleep(0.1)
        except Exception as e:
            log(e, "consolereader_exceptions", logdir)

    def handler(self, sig, logdir):
        log(sig, "consolereader", logdir)
        return False

    def getConsoleOut(self):
        consout = win32file.CreateFile(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            0,
        )

        return PyConsoleScreenBufferType(consout)

    def initConsole(self, consout, c=None, r=None):
        # Window size can't be larger than maximum window size
        consinfo = consout.GetConsoleScreenBufferInfo()
        maxwinsize = consinfo["MaximumWindowSize"]
        rect = PySMALL_RECTType(
            0, 0, min(maxwinsize.X - 1, 79), min(maxwinsize.Y - 1, 24)
        )
        consout.SetConsoleWindowInfo(True, rect)
        # Buffer size can't be smaller than window size
        size = PyCOORDType(
            max(rect.Right + 1, c or 80), max(rect.Bottom + 1, r or 16000)
        )
        consout.SetConsoleScreenBufferSize(size)
        pos = PyCOORDType(0, 0)
        consout.FillConsoleOutputCharacter(" ", size.X * size.Y, pos)

    def suspendThread(self):
        """Pauses the main thread of the child process."""
        handle = windll.kernel32.OpenThread(THREAD_SUSPEND_RESUME, 0, self.__tid)
        SuspendThread(handle)

    def resumeThread(self):
        """Un-pauses the main thread of the child process."""
        handle = windll.kernel32.OpenThread(THREAD_SUSPEND_RESUME, 0, self.__tid)
        ResumeThread(handle)


class searcher_string:
    """This is a plain string search helper for the spawn.expect_any() method.

    Attributes:

        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the matching string itself
    """

    def __init__(self, strings):
        """This creates an instance of searcher_string. This argument 'strings'
        may be a list; a sequence of strings; or the EOF or TIMEOUT types.
        """
        self.eof_index = -1
        self.timeout_index = -1
        self._strings = []
        for n, s in zip(list(range(len(strings))), strings):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._strings.append((n, s))

    def __str__(self):
        """This returns a human-readable string that represents the state of
        the object."""
        ss = [(ns[0], '    %d: "%s"' % ns) for ns in self._strings]
        ss.append((-1, "searcher_string:"))
        if self.eof_index >= 0:
            ss.append((self.eof_index, "    %d: EOF" % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, "    %d: TIMEOUT" % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss))[1]
        return "\n".join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):
        """This searches 'buffer' for the first occurence of one of the search
        strings.  'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before. It helps to avoid
        searching the same, possibly big, buffer over and over again.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, this returns -1."""
        absurd_match = len(buffer)
        first_match = absurd_match

        # 'freshlen' helps a lot here. Further optimizations could
        # possibly include:
        #
        # using something like the Boyer-Moore Fast String Searching
        # Algorithm; pre-compiling the search through a list of
        # strings into something that can scan the input once to
        # search for all N strings; realize that if we search for
        # ['bar', 'baz'] and the input is '...foo' we need not bother
        # rescanning until we've read three more bytes.
        #
        # Sadly, I don't know enough about this interesting topic. /grahn

        best_index = None
        best_match = None
        for index, s in self._strings:
            if searchwindowsize is None:
                # the match, if any, can only be in the fresh data,
                # or at the very end of the old data
                offset = -(freshlen + len(s))
            else:
                # better obey searchwindowsize
                offset = -searchwindowsize
            n = buffer.find(s, offset)
            if 0 <= n < first_match:
                first_match = n
                best_index, best_match = index, s
        if first_match == absurd_match:
            return -1
        self.match = best_match
        self.start = first_match
        self.end = self.start + len(self.match)
        return best_index


class searcher_re:
    """Regular expression string search helper for the spawn.expect_any() method.

    Attributes:

        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the re.match object returned by a succesful re.search

    """

    def __init__(self, patterns):
        """This creates an instance that searches for 'patterns' Where
        'patterns' may be a list or other sequence of compiled regular
        expressions, or the EOF or TIMEOUT types.
        """
        self.eof_index = -1
        self.timeout_index = -1
        self._searches = []
        for n, s in zip(list(range(len(patterns))), patterns):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._searches.append((n, s))

    def __str__(self):
        """Return a human-readable string that represents the state of the object."""
        ss = [
            (n, '    %d: re.compile(r"%s")' % (n, str(s.pattern)))
            for n, s in self._searches
        ]
        ss.append((-1, "searcher_re:"))
        if self.eof_index >= 0:
            ss.append((self.eof_index, "    %d: EOF" % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, "    %d: TIMEOUT" % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss))[1]
        return "\n".join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):
        """Search 'buffer' for the first occurence of one of the regular expressions.

        'freshlen' must indicate the number of bytes at the end of 'buffer' which have
        not been searched before.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets 'start',
        'end' and 'match'. Otherwise, returns -1.
        """
        absurd_match = len(buffer)
        first_match = absurd_match
        the_match = None
        best_index = None
        # 'freshlen' doesn't help here -- we cannot predict the
        # length of a match, and the re module provides no help.
        if searchwindowsize is None:
            searchstart = 0
        else:
            searchstart = max(0, len(buffer) - searchwindowsize)
        for index, s in self._searches:
            match = s.search(buffer, searchstart)
            if match is None:
                continue
            n = match.start()
            if n < first_match:
                first_match = n
                the_match = match
                best_index = index
        if first_match == absurd_match:
            return -1
        self.start = first_match
        self.match = the_match
        self.end = self.match.end()
        return best_index


def log(e, suffix="", logdir=None):
    if isinstance(e, Exception):
        # Get the full traceback
        e = traceback.format_exc()
    # if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
    #     # Only try to print if stdout is a tty, otherwise we might get
    #     # an 'invalid handle' exception
    #     print e
    if not logdir:
        if getattr(sys, "frozen", False):
            logdir = appname
        else:
            logdir = os.path.split(os.path.dirname(os.path.abspath(__file__)))
            if logdir[-1] == "lib":
                logdir.pop()
            logdir = logdir[-1]
    if sys.platform == "win32":
        parent = SHGetSpecialFolderPath(0, CSIDL_APPDATA, 1)
    elif sys.platform == "darwin":
        parent = os.path.join(os.path.expanduser("~"), "Library", "Logs")
    else:
        parent = os.getenv("XDG_DATA_HOME", os.path.expandvars("$HOME/.local/share"))
    # If old user data directory exists, use its basename
    if logdir == appname and os.path.isdir(os.path.join(parent, "dispcalGUI")):
        logdir = "dispcalGUI"
    logdir = os.path.join(parent, logdir)
    if sys.platform != "darwin":
        logdir = os.path.join(logdir, "logs")
    if not os.path.exists(logdir):
        try:
            os.makedirs(logdir)
        except OSError:
            pass
    if os.path.isdir(logdir) and os.access(logdir, os.W_OK):
        logfile = os.path.join(logdir, "wexpect%s.log" % suffix)
        if os.path.isfile(logfile):
            try:
                logstat = os.stat(logfile)
            except Exception:
                pass
            else:
                try:
                    mtime = time.localtime(logstat.st_mtime)
                except ValueError:
                    # This can happen on Windows because localtime() is buggy on
                    # that platform. See:
                    # http://stackoverflow.com/questions/4434629/zipfile-module-in-python-runtime-problems
                    # http://bugs.python.org/issue1760357
                    # To overcome this problem, we ignore the real modification
                    # date and force a rollover
                    mtime = time.localtime(time.time() - 60 * 60 * 24)
                if time.localtime()[:3] > mtime[:3]:
                    # do rollover
                    try:
                        os.remove(logfile)
                    except Exception:
                        pass
        try:
            with open(logfile, "a", encoding="utf-8") as fout:
                ts = time.time()
                fout.write(
                    "%s,%s %s\n"
                    % (
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                        ("%3f" % (ts - int(ts)))[2:5],
                        e,
                    )
                )
        except Exception:
            pass


def excepthook(etype, value, tb):
    log("".join(traceback.format_exception(etype, value, tb)))


# sys.excepthook = excepthook


def which(filename):
    """This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None.
    """
    # Special case where filename already contains a path.
    if os.path.dirname(filename) != "":
        if os.access(filename, os.X_OK):
            return filename

    if "PATH" not in os.environ or os.environ["PATH"] == "":
        p = os.defpath
    else:
        p = os.environ["PATH"]

    # Oddly enough this was the one line that made Pexpect
    # incompatible with Python 1.5.2.
    # pathlist = p.split (os.pathsep)
    pathlist = string.split(p, os.pathsep)

    for path in pathlist:
        f = os.path.join(path, filename)
        if os.access(f, os.X_OK):
            return f
    return None


def join_args(args):
    """Join arguments into a command line.

    It quotes all arguments that contain spaces or any of the characters:

        ^!$%&()[]{}=;'+,`~
    """
    command_line = []
    for arg in args:
        if isinstance(arg, bytes):
            arg = arg.decode()
        if re.search(r"[^!$%&()[]{}=;'+,`~\s]", arg):
            arg = '"%s"' % arg
        command_line.append(arg)
    return " ".join(command_line)


def split_command_line(command_line):
    """This splits a command line into a list of arguments. It splits arguments
    on spaces, but handles embedded quotes, doublequotes, and escaped
    characters. It's impossible to do this with a regular expression, so I
    wrote a little state machine to parse the command line.
    """
    arg_list = []
    arg = ""

    # Constants to name the states we can be in.
    state_basic = 0
    state_esc = 1
    state_singlequote = 2
    state_doublequote = 3
    state_whitespace = 4  # The state of consuming whitespace between commands.
    state = state_basic
    state_backup = state

    for c in command_line:
        if (
            state not in (state_esc, state_singlequote) and c == "\\"
        ):  # Escape the next character
            state_backup = state
            state = state_esc
        elif state == state_basic or state == state_whitespace:
            if c == r"'":  # Handle single quote
                state = state_singlequote
            elif c == r'"':  # Handle double quote
                state = state_doublequote
            elif c.isspace():
                # Add arg to arg_list if we aren't in the middle of whitespace.
                if state == state_whitespace:
                    None  # Do nothing.
                else:
                    arg_list.append(arg)
                    arg = ""
                    state = state_whitespace
            else:
                arg = arg + c
                state = state_basic
        elif state == state_esc:
            # Follow bash escaping rules within double quotes:
            # http://www.gnu.org/software/bash/manual/html_node/Double-Quotes.html
            if state_backup == state_doublequote and c not in (
                "$",
                "`",
                '"',
                "\\",
                "\n",
            ):
                arg += "\\"
            arg = arg + c
            if state_backup != state_whitespace:
                state = state_backup
            else:
                state = state_basic
        elif state == state_singlequote:
            if c == r"'":
                state = state_basic
            else:
                arg = arg + c
        elif state == state_doublequote:
            if c == r'"':
                state = state_basic
            else:
                arg = arg + c

    if arg != "":
        arg_list.append(arg)
    return arg_list
