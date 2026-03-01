"""DisplayCAL main module."""

from __future__ import annotations

import atexit
import errno
import getpass
import glob
import os
import platform
import socket
import subprocess as sp
import sys
import threading
from time import sleep
from typing import TYPE_CHECKING, Any

# Python version check
from DisplayCAL.meta import PY_MAXVERSION, PY_MINVERSION

PYVER = sys.version_info[:2]
if PYVER < PY_MINVERSION or PYVER > PY_MAXVERSION:
    raise RuntimeError(
        "Need Python version >= {} <= {}, got {}".format(
            ".".join(str(n) for n in PY_MINVERSION),
            ".".join(str(n) for n in PY_MAXVERSION),
            sys.version.split()[0],
        )
    )

import distro

from DisplayCAL import localization as lang
from DisplayCAL.config import (
    APPBASENAME,
    CONFIG_HOME,
    DATA_HOME,
    ENC,
    EXE_EXT,
    EXENAME,
    FS_ENC,
    LOGDIR,
    PYNAME,
    RES_FILES,
    RUNTYPE,
    get_data_path,
    getcfg,
    initcfg,
)
from DisplayCAL.debughelpers import ResourceError, handle_error
from DisplayCAL.log import LOG
from DisplayCAL.meta import VERSION_STRING
from DisplayCAL.meta import (
    NAME as APPNAME,
)
from DisplayCAL.multiprocess import mp
from DisplayCAL.options import VERBOSE
from DisplayCAL.util_os import FileLock, LockingError, UnlockingError

if sys.platform == "win32":
    from DisplayCAL.util_win import win_ver
elif sys.platform == "darwin":
    from platform import mac_ver

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType
    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


def _excepthook(
    etype: None | type[BaseException],
    value: None | BaseException,
    tb: None | TracebackType,
) -> None:
    """Global exception handler.

    Args:
        etype (type[BaseException]): Exception type.
        value (BaseException): Exception instance.
        tb (TracebackType): Traceback object.
    """
    handle_error((etype, value, tb))


sys.excepthook = _excepthook

MULTI_INSTANCE_APP_NAMES = (
    "curve-viewer",
    "profile-info",
    "scripting-client",
    "synthprofile",
    "testchart-editor",
)
"""Allow multiple instances only for curve viewer, profile info,
scripting client, synthetic profile creator and testchart editor."""


def _main(
    module: str, name: str, app_lock_file_name: str, probe_ports: bool = True
) -> None:
    """Main function.

    Args:
        module (str): Module name.
        name (str): Application name.
        app_lock_file_name (str): Lock file name.
        probe_ports (bool, optional): Whether to probe ports of other
            instances. Default is True.
    """
    with AppLock(
        app_lock_file_name, "a+", False, module in MULTI_INSTANCE_APP_NAMES
    ) as lock:
        print(f"Acquired lock file: {lock}")
        LOG("=" * 80)

        print_system_version_information()
        initialize_fault_handler()
        initialize_wx_module()
        set_high_dpi_awareness()
        initcfg(module)
        lock_to_pids_and_ports = {}
        if probe_ports and not probe_used_ports(
            module, name, app_lock_file_name, lock, lock_to_pids_and_ports
        ):
            return

    if not lock:
        # If a race condition occurs, do not start another instance
        print("Not starting another instance.")
        return

    initialize_app(module, app_lock_file_name, lock_to_pids_and_ports)
    run_app(module)


def print_application_version() -> None:
    """Print application version."""
    if VERBOSE >= 1:
        version = VERSION_STRING
        print(PYNAME + RUNTYPE, version, "")


def print_os_version() -> None:
    """Print OS version."""
    if sys.platform == "darwin":
        # Python's platform.platform output is useless under Mac OS X
        # (e.g. 'Darwin-15.0.0-x86_64-i386-64bit' for Mac OS X 10.11 El Capitan)
        print(f"Mac OS X {mac_ver()[0]} {mac_ver()[-1]}")
    elif sys.platform == "win32":
        machine = platform.machine()
        print(
            *[v for v in win_ver() if v]
            + [
                {"AMD64": "x86_64"}.get(machine, machine),
            ]
        )
    else:
        # Linux
        print(
            f"{distro.id()} {distro.version()} {distro.codename()}",
            platform.machine(),
        )


def print_python_version() -> None:
    """Print Python version."""
    print(f"Python {sys.version}")


def print_cafile_details() -> None:
    """Print CA file details."""
    cafile = os.getenv("SSL_CERT_FILE")
    if cafile:
        print("CA file", cafile)


def print_system_version_information() -> None:
    """Print system version information."""
    print_application_version()
    print_os_version()
    print_python_version()
    print_cafile_details()


def initialize_fault_handler() -> None:
    """Initialize faulthandler to log crashes."""
    # Enable faulthandler
    try:
        import faulthandler
    except Exception as exception:
        print(exception)
    else:
        try:
            faulthandler.enable(open(os.path.join(LOGDIR, f"{PYNAME}-fault.log"), "w"))  # noqa: SIM115
        except Exception as exception:
            print(exception)
        else:
            print("Faulthandler", getattr(faulthandler, "__version__", ""))


def initialize_wx_module() -> None:
    """Initialize wx module."""
    from DisplayCAL.wx_addons import wx

    if "phoenix" in wx.PlatformInfo:
        # py2exe helper so wx.xml gets picked up
        from wx import xml  # noqa: F401
    print(f"wxPython {wx.version()}")
    print(f"Encoding: {ENC}")
    print(f"File system encoding: {FS_ENC}")


def set_high_dpi_awareness() -> None:
    """Set high DPI awareness on Windows 8.1 and later."""
    if sys.platform != "win32" or sys.getwindowsversion() < (6, 2):
        return

    # HighDPI support
    try:
        import ctypes

        shcore = ctypes.windll.shcore
    except Exception as exception:
        print("Warning - could not load shcore:", exception)
    else:
        if hasattr(shcore, "SetProcessDpiAwareness"):
            try:
                # 1 = System DPI aware (wxWpython currently does not
                # support per-monitor DPI)
                shcore.SetProcessDpiAwareness(1)
            except Exception as exception:
                print("Warning - SetProcessDpiAwareness() failed:", exception)
        else:
            print("Warning - SetProcessDpiAwareness not found in shcore")


def probe_used_ports(
    module: str,
    name: str,
    app_lock_file_name: str,
    lock: AppLock,
    lock_to_pids_and_ports: dict,
) -> bool:
    """Probe used ports to check for other instances.

    Args:
        module (str): Module name.
        name (str): Application name.
        app_lock_file_name (str): Lock file name.
        lock (AppLock): Lock file object.
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.

    Returns:
        bool: True if no other instance is running or multiple instances
            are allowed, False otherwise.
    """
    check_for_currently_used_ports(app_lock_file_name, lock, lock_to_pids_and_ports)

    if module in MULTI_INSTANCE_APP_NAMES:
        return True

    incoming = check_lock_files_and_probe_ports(
        module, app_lock_file_name, lock, lock_to_pids_and_ports
    )

    if incoming is not None:
        # Other instance running?
        lang.init()
        if incoming == "ok":
            # Successfully sent our request
            print(lang.getstr("app.otherinstance.notified"))
        elif module == "apply-profiles":
            print("Not starting another instance.")
        else:
            # Other instance busy?
            handle_error(lang.getstr("app.otherinstance", name))
        # Exit
        return False
    return True


def check_for_currently_used_ports(
    app_lock_file_name: str,
    lock: AppLock,
    lock_to_pids_and_ports: dict,
) -> None:
    """Check for currently used ports.

    Args:
        app_lock_file_name (str): Lock file name.
        lock (AppLock): Lock file object.
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.
    """
    lockfilenames = glob.glob(os.path.join(CONFIG_HOME, "*.lock"))
    for lockfilename in lockfilenames:
        try:
            if lock and lockfilename == app_lock_file_name:
                lockfile = lock
                lock.seek(0)
            else:
                lockfile = AppLock(lockfilename, "r", False, True)
            if lockfile:
                update_lock_to_pid_ports(lock_to_pids_and_ports, lockfilename, lockfile)
            if not lock or lockfilename != app_lock_file_name:
                lockfile.unlock()
        except OSError as exception:
            # This shouldn't happen
            print(f"Warning - could not read lockfile {lockfilename}:", exception)


def update_lock_to_pid_ports(
    lock_to_pids_and_ports: dict,
    lockfilename: str,
    lockfile: AppLock,
) -> None:
    """Update mapping of lock files to PIDs and ports.

    Args:
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.
        lockfilename (str): Lock file name.
        lockfile (AppLock): Lock file object.
    """
    if lockfilename not in lock_to_pids_and_ports:
        lock_to_pids_and_ports[lockfilename] = []
    for ln, line in enumerate(lockfile.read().splitlines(), 1):
        if ":" in line:
            # DisplayCAL >= 3.8.8.2 with localhost blocked
            pid, port = line.split(":", 1)
            if pid:
                try:
                    pid = int(pid)
                except ValueError:
                    # This shouldn't happen
                    print(
                        "Warning - couldn't parse PID as int: "
                        f"{pid!r} ({lockfilename} line {ln})"
                    )
                    pid = None
                else:
                    print("Existing client using PID", pid)
        else:
            # DisplayCAL <= 3.8.8.1 or localhost ok
            pid = None
            port = line
        if port:
            try:
                port = int(port)
            except ValueError:
                # This shouldn't happen
                print(
                    "Warning - couldn't parse port as int: "
                    f"{port!r} ({lockfilename} line {ln})"
                )
                port = None
            else:
                print("Existing client using port", port)
        if pid or port:
            lock_to_pids_and_ports[lockfilename].append((pid, port))


def check_lock_files_and_probe_ports(
    module: str,
    app_lock_file_name: str,
    lock: AppLock,
    lock_to_pids_and_ports: dict,
) -> None | str:
    """Check lockfile(s) and probe port(s).

    Args:
        module (str): Module name.
        app_lock_file_name (str): Lock file name.
        lock (AppLock): Lock file object.
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.

    Returns:
        None | str: Incoming status.
    """
    host = "127.0.0.1"

    # Check lockfile(s) and probe port(s)
    incoming = None
    for lockfilename in [app_lock_file_name]:
        incoming = None
        pids_ports = lock_to_pids_and_ports.get(lockfilename)
        if pids_ports:
            incoming = connect_and_notify_running_instance(
                module, lock, host, pids_ports
            )
            pid, _ = pids_ports[0]
        else:
            pid = None
        if not incoming:
            incoming = terminate_conflicting_instance(
                module,
                lockfilename,
                lock,
                pid,
                incoming,
            )

        if incoming == "ok":
            # Successfully sent our request
            if module == "apply-profiles":
                # Wait for lockfile to be removed, in which case
                # we know the running instance has successfully
                # closed.
                print(
                    "Waiting for existing instance to exit and delete lockfile",
                    lockfilename,
                )
                while os.path.isfile(lockfilename):
                    sleep(0.05)
                lock.lock()
                print("Existing instance exited.")
                incoming = None
                lock_to_pids_and_ports.pop(lockfilename, None)
            break

    return incoming


def connect_and_notify_running_instance(
    module: str,
    lock: AppLock,
    host: str,
    pids_ports: list,
) -> None | str:
    """Connect to running instance and notify it.

    Args:
        module (str): Module name.
        lock (AppLock): Lock file object.
        host (str): Host address.
        pids_ports (list): List of tuples containing PIDs and ports.

    Returns:
        None | str: Incoming status.
    """
    _, port = pids_ports[0]
    incoming = None
    appsocket = AppSocket()
    if not appsocket or not port:
        return incoming

    print(f"Connecting to {port}...")
    if appsocket.connect(host, port):
        print("Connected to", port)
        # Other instance already running?
        # Get appname to check if expected app is actually
        # running under that port
        print("Getting instance name")
        if appsocket.send("getappname"):
            print("Sent scripting request, awaiting response...")
            data_read = appsocket.read()
            incoming = data_read.rstrip("\4")
            print(f"Got response: {incoming!r}")
            # translate incoming values
            incoming = {
                PYNAME: PYNAME,
                False: False,
                None: False,
                "": False,
            }.get(incoming)

    while incoming:
        # Send args as UTF-8
        if module == "apply-profiles":
            # Always try to close currently running instance
            print("Closing existing instance")
            cmd = "exit" if incoming == PYNAME else "close"
            data = [cmd]
            lock.unlock()
        else:
            # Send module/appname to notify running app
            print("Notifying existing instance")
            data = [module or APPNAME]
            if module != "3DLUT-maker":
                for arg in sys.argv[1:]:
                    data.append(str(arg))
        data = sp.list2cmdline(data)
        if appsocket.send(data):
            print("Sent scripting request, awaiting response...")
            data_read = appsocket.read()
            incoming = data_read.rstrip("\4")
            print(f"Got response: {incoming!r}")
            if module == "apply-profiles":
                if incoming == "":
                    # Successfully sent our close request.
                    incoming = "ok"
                elif incoming == "invalid" and cmd == "exit":
                    # < 3.8.8.1 didn't have exit command
                    continue
        break
    appsocket.close()
    return incoming


def terminate_conflicting_instance(
    module: str,
    lockfilename: str,
    lock: AppLock,
    pid: int,
    incoming: None | str,
) -> None | str:
    """Terminate conflicting instance by PID.

    Args:
        module (str): Module name.
        lockfilename (str): Lock file name.
        lock (AppLock): Lock file object.
        pid (int): PID of the process to terminate.
        incoming (None | str): Incoming status.

    Returns:
        None | str: Updated incoming status.
    """
    if sys.platform != "win32":
        return incoming

    import pywintypes
    import win32ts

    opid = os.getpid()

    try:
        osid = win32ts.ProcessIdToSessionId(opid)
    except pywintypes.error as exception:
        print("Enumerating processes failed:", exception)
        osid = None

    try:
        processes = win32ts.WTSEnumerateProcesses()
    except pywintypes.error as exception:
        print("Enumerating processes failed:", exception)
    else:
        appname_lower = APPNAME.lower()
        exename_lower = EXENAME.lower()
        pyexe_lower = (
            f"{appname_lower}-{module}{EXE_EXT}"
            if module
            else f"{appname_lower}{EXE_EXT}"
        )
        incoming = None
        for sid, pid2, basename, _usid in processes:
            basename_lower = basename.lower()
            # Optimized condition for process matching
            is_pid_match = pid and pid2 == pid and basename_lower == exename_lower
            is_session_exe_match = (
                osid is None or sid == osid
            ) and basename_lower == pyexe_lower
            if not (is_pid_match or is_session_exe_match) or pid2 == opid:
                continue
            # Other instance running
            incoming = False
            if module != "apply-profiles":
                continue
            if not os.path.isfile(lockfilename):
                create_dummy_lockfile(lockfilename)
            print(
                "Closing existing instance with PID",
                pid2,
            )
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = sp.SW_HIDE
            lock.unlock()
            incoming = terminate_running_instance(incoming, pid2, startupinfo)

    return incoming


def create_dummy_lockfile(lockfilename: str) -> None:
    """Create a dummy lockfile.

    Args:
        lockfilename (str): Lock file name.
    """
    # Create dummy lockfile
    try:
        with open(lockfilename, "w"):
            pass
    except OSError as exception:
        print(
            f"Warning - could not create dummy lockfile {lockfilename}: {exception!r}"
        )
    else:
        print(
            "Warning - had to create dummy lockfile",
            lockfilename,
        )


def terminate_running_instance(
    incoming: None | str,
    pid2: int,
    startupinfo: sp.STARTUPINFO,
) -> None | str:
    """Terminate running instance by PID.

    Args:
        incoming (None | str): Incoming status.
        pid2 (int): PID of the process to terminate.
        startupinfo (subprocess.STARTUPINFO): Startup info for subprocess.

    Returns:
        None | str: Updated incoming status.
    """
    try:
        p = sp.Popen(
            ["taskkill", "/PID", f"{pid2}"],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            startupinfo=startupinfo,
        )
        stdout, stderr = p.communicate()
    except Exception as exception:
        print(exception)
    else:
        print(stdout)
        if not p.returncode:
            # Successfully sent our close request.
            incoming = "ok"
    return incoming


def initialize_app(
    module: str, app_lock_file_name: str, lock_to_pids_and_ports: dict
) -> None:
    """Initialize application.

    Args:
        module (str): Module name.
        app_lock_file_name (str): Lock file name.
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.
    """
    opid = os.getpid()
    defaultport = getcfg("app.port")
    # Use exclusive lock during app startup
    with AppLock(app_lock_file_name, "a+", True, True) as lock:
        # Create listening socket
        if appsocket := AppSocket():
            initialize_socket(lock_to_pids_and_ports, defaultport, appsocket)
        port = getattr(sys, "_appsocket_port", "")
        update_lock_file_content(module, opid, lock, port)
        atexit.register(lambda: print("Ran application exit handlers"))
        from DisplayCAL.wx_windows import BaseApp

        BaseApp.register_exitfunc(_exit, app_lock_file_name, port)
        check_for_required_resource_files(module)
        create_main_data_dir()


def initialize_socket(
    lock_to_pids_and_ports: dict,
    defaultport: int,
    appsocket: AppSocket,
) -> None:
    """Initialize listening socket.

    Args:
        lock_to_pids_and_ports (dict): Mapping of lock files to PIDs and ports.
        defaultport (int): Default port to use.
        appsocket (AppSocket): Socket object.
    """
    host = "127.0.0.1"
    if sys.platform != "win32":
        # https://docs.microsoft.com/de-de/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse#using-so_reuseaddr
        # From the above link: "The SO_REUSEADDR socket option allows
        # a socket to forcibly bind to a port in use by another socket".
        # Note that this is different from the behavior under Linux/BSD,
        # where a socket can only be (re-)bound if no active listening
        # socket is already bound to the address.
        # Consequently, we don't use SO_REUSEADDR under Windows.
        appsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sys._appsocket = appsocket.socket
    if getcfg("app.allow_network_clients"):
        host = ""
    used_ports = [
        pid_port[1]
        for pids_ports in list(lock_to_pids_and_ports.values())
        for pid_port in pids_ports
    ]
    candidate_ports = [0]
    if defaultport not in used_ports:
        candidate_ports.insert(0, defaultport)

    for port in candidate_ports:
        try:
            sys._appsocket.bind((host, port))
        except OSError as exception:
            if port == 0:
                print(
                    f"Warning - could not bind to {host}:{port}:",
                    exception,
                )
                del sys._appsocket
                break
        else:
            try:
                sys._appsocket.settimeout(0.2)
            except OSError as exception:
                print("Warning - could not set socket timeout:", exception)
                del sys._appsocket
                break
            try:
                print("listening")
                sys._appsocket.listen(1)
            except OSError as exception:
                print("Warning - could not listen on socket:", exception)
                del sys._appsocket
                break
            try:
                port = sys._appsocket.getsockname()[1]
            except OSError as exception:
                print("Warning - could not get socket address:", exception)
                del sys._appsocket
                break
            sys._appsocket_port = port
            break


def update_lock_file_content(module: str, opid: int, lock: AppLock, port: int) -> None:
    """Update lock file content.

    Args:
        module (str): Module name.
        opid (int): Our PID.
        lock (AppLock): Lock file object.
        port (int): Our listening port.
    """
    lock.seek(0)
    if module not in MULTI_INSTANCE_APP_NAMES:
        lock.truncate(0)
    if not port:
        print(f"writing to lock file: opid: {opid}  port: {port}")
        lock.write(f"{opid}:{port}")
    else:
        print(f"writing to lock file: port: {port}")
        lock.write(port)
    lock.flush()


def check_for_required_resource_files(module: str) -> None:
    """Check for required resource files.

    Args:
        module (str): Module name.
    """
    # Check for required resource files
    mod2res = {
        "3DLUT-maker": ["xrc/3dlut.xrc"],
        "curve-viewer": [],
        "profile-info": [],
        "scripting-client": [],
        "synthprofile": ["xrc/synthicc.xrc"],
        "testchart-editor": [],
        "VRML-to-X3D-converter": [],
    }
    for filename in mod2res.get(module, RES_FILES):
        path = get_data_path(os.path.sep.join(filename.split("/")))
        if not path or not os.path.isfile(path):
            lang.init()
            raise ResourceError(
                lang.getstr("resources.notfound.error") + "\n" + filename
            )


def create_main_data_dir() -> None:
    """Create main data directory if it does not exist."""
    # Create main data dir if it does not exist
    if not os.path.exists(DATA_HOME):
        try:
            os.makedirs(DATA_HOME)
        except Exception:
            handle_error(
                UserWarning(f"Warning - could not create directory '{DATA_HOME}'")
            )
    elif sys.platform == "darwin":
        # Check & fix permissions if necessary
        user = getpass.getuser()
        script = [
            f"chown -R '{user}' '{directory}'"
            for directory in (CONFIG_HOME, DATA_HOME, LOGDIR)
            if os.path.isdir(directory) and not os.access(directory, os.W_OK)
        ]
        if script:
            sp.call(
                [  # noqa: S607
                    "osascript",
                    "-e",
                    'do shell script "{}" with administrator privileges'.format(
                        ";".join(script).encode(FS_ENC),
                    ),
                ]
            )


def run_app(module: str) -> None:
    """Run the application.

    Args:
        module (str): Module name.
    """
    # Initialize & run
    if module == "3DLUT-maker":
        from DisplayCAL.wx_lut_3d_frame import main
    elif module == "curve-viewer":
        from DisplayCAL.wx_lut_viewer import main
    elif module == "profile-info":
        from DisplayCAL.wx_profile_info import main
    elif module == "scripting-client":
        from DisplayCAL.wx_scripting_client import main
    elif module == "synthprofile":
        from DisplayCAL.wx_synth_icc_frame import main
    elif module == "testchart-editor":
        from DisplayCAL.wx_testchart_editor import main
    elif module == "VRML-to-X3D-converter":
        from DisplayCAL.wx_vrml_2_x3d import main
    elif module == "apply-profiles":
        from DisplayCAL.profile_loader import main
    else:
        from DisplayCAL.display_cal import main

    # Run main after releasing lock
    main()


def main(module: None | str = None) -> None:
    """Main entry point.

    Args:
        module (None | str, optional): Module name. Default is None.
    """
    mp.freeze_support()
    if mp.current_process().name != "MainProcess":
        return
    name = f"{APPBASENAME}-{module}" if module else APPBASENAME
    app_lock_file_name = os.path.join(CONFIG_HOME, f"{name}.lock")
    try:
        _main(module, name, app_lock_file_name)
    except Exception as exception:
        if isinstance(exception, ResourceError):
            error = exception
        else:
            error = Error(f"Fatal error: {exception}")
        handle_error(error)
        _exit(app_lock_file_name, getattr(sys, "_appsocket_port", ""))


def _exit(lockfilename: str, oport: int) -> None:
    """Application exit handler.

    Args:
        lockfilename (str): Lock file name.
        oport (int): Our listening port.
    """
    for process in mp.active_children():
        if "Manager" not in process.name:
            print("Terminating zombie process", process.name)
            process.terminate()
            print(process.name, "terminated")

    for thread in threading.enumerate():
        if (
            thread.is_alive()
            and thread is not threading.current_thread()
            and not thread.daemon
        ):
            print(f"Waiting for thread {thread.name} to exit")
            thread.join()
            print(thread.name, "exited")

    if lockfilename and os.path.isfile(lockfilename):
        with AppLock(lockfilename, "r+", False, True) as lock:
            _update_lockfile(lockfilename, oport, lock)

    print("Exiting", PYNAME)


def _update_lockfile(lockfilename: str, oport: int, lock: AppLock) -> None:
    """Update lockfile by removing our own PID & port.

    Args:
        lockfilename (str): Lock file name.
        oport (int): Our listening port.
        lock (AppLock): Lock file object.
    """
    if not lock:
        return
    # Each lockfile may contain multiple ports of running instances
    try:
        pids_ports = lock.read().splitlines()
    except OSError as exception:
        print(f"Warning - could not read lockfile {lockfilename}: {exception!r}")
        # filtered_pids_ports = []
        return

    opid = os.getpid()

    remove_instances_if_not_running(pids_ports, opid, oport)
    check_filtered_pids_ports(lockfilename, lock, pids_ports)


def remove_instances_if_not_running(
    pids_ports: list,
    opid: int,
    oport: int,
) -> None:
    """Remove our own PID & port from list of PIDs & ports if not running.

    Args:
        pids_ports (list): List of PIDs & ports.
        opid (int): Our PID.
        oport (int): Our listening port.
    """
    # Determine if instances still running. If not still running,
    # remove from list of ports
    for i in reversed(range(len(pids_ports))):
        pid_port = pids_ports[i]
        if ":" in pid_port:
            # DisplayCAL >= 3.8.8.2 with localhost blocked
            pid, port = pid_port.split(":", 1)
            if pid:
                try:
                    pid = int(pid)
                except ValueError:
                    # This shouldn't happen
                    pid = None
        else:
            # DisplayCAL <= 3.8.8.1 or localhost ok
            pid = None
            port = pid_port
        if port:
            try:
                port = int(port)
            except ValueError:
                # This shouldn't happen
                continue
        if (pid and pid == opid and not port) or (port and port == oport):
            # Remove ourself
            pids_ports[i] = ""
            continue
        if not port:
            continue
        appsocket = AppSocket()
        if not appsocket:
            break
        if not appsocket.connect("127.0.0.1", port):
            # Other instance probably died
            pids_ports[i] = ""
        appsocket.close()


def check_filtered_pids_ports(
    lockfilename: str,
    lock: AppLock,
    pids_ports: list,
) -> None:
    """Check filtered PIDs & ports and update or remove lockfile.

    Args:
        lockfilename (str): Lock file name.
        lock (AppLock): Lock file object.
        pids_ports (list): List of PIDs & ports.
    """
    # Filtered PIDs & ports (only used for checking)
    filtered_pids_ports = [pid_port for pid_port in pids_ports if pid_port]
    if filtered_pids_ports:
        # Write updated lockfile
        try:
            lock.seek(0)
            lock.truncate(0)
        except OSError as exception:
            print(f"Warning - could not update lockfile {lockfilename}: {exception!r}")
        else:
            lock.write("\n".join(pids_ports))
    else:
        lock.close()
        try:
            os.remove(lockfilename)
        except OSError as exception:
            print(f"Warning - could not remove lockfile {lockfilename}: {exception!r}")


def main_3dlut_maker() -> None:
    """Launch the 3D LUT maker."""
    main("3DLUT-maker")


def main_curve_viewer() -> None:
    """Launch the 3D LUT viewer."""
    main("curve-viewer")


def main_profile_info() -> None:
    """Launch the profile info editor."""
    main("profile-info")


def main_synthprofile() -> None:
    """Launch the synthetic profile creator."""
    main("synthprofile")


def main_testchart_editor() -> None:
    """Launch the testchart editor."""
    main("testchart-editor")


class AppLock:
    """Lock file wrapper class.

    Args:
        lockfilename (str): Lock file name.
        mode (str): File open mode, e.g. 'r', 'a+', etc.
        exclusive (bool, optional): Whether to acquire an exclusive lock.
            Default is False.
        blocking (bool, optional): Whether to wait until the lock is acquired.
            Default is False.
    """

    def __init__(
        self,
        lockfilename: str,
        mode: str,
        exclusive: bool = False,
        blocking: bool = False,
    ) -> None:
        self._lockfilename = lockfilename
        self._mode = mode
        self._lockfile = None
        self._lock = None
        self._exclusive = exclusive
        self._blocking = blocking
        self.lock()

    def __enter__(self) -> Self:
        """Context manager enter method.

        Returns:
            Self: The AppLock instance.
        """
        return self

    def __exit__(
        self,
        etype: None | type[BaseException],
        value: None | BaseException,
        traceback: None | TracebackType,
    ) -> None:
        """Release lock and close lockfile.

        Args:
            etype (None | type[BaseException]): Exception type.
            value (None | BaseException): Exception instance.
            traceback (None | TracebackType): Traceback object.
        """
        self.unlock()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Return attribute of lockfile.

        Args:
            name (str): Attribute name.

        Returns:
            Any: Attribute of lockfile.
        """
        return getattr(self._lockfile, name)

    def __iter__(self) -> None | Iterator:
        """Return iterator for lockfile.

        Returns:
            None | Iterator: Iterator for lockfile, or None if lockfile
                is not available.
        """
        return self._lockfile

    def __bool__(self) -> bool:
        """Return True if lockfile was successfully created and locked."""
        return bool(self._lock)

    def lock(self) -> bool:
        """Create and lock lockfile.

        Returns:
            bool: True on success, False on failure.
        """
        lockdir = os.path.dirname(self._lockfilename)
        try:
            if not os.path.isdir(lockdir):
                os.makedirs(lockdir)
            # Create lockfile
            self._lockfile = open(self._lockfilename, self._mode)  # noqa: SIM115
        except OSError as exception:
            # This shouldn't happen
            print(f"Error - could not open lockfile {self._lockfilename}:", exception)
        else:
            try:
                self._lock = FileLock(self._lockfile, self._exclusive, self._blocking)
            except LockingError:
                pass
            except OSError as exception:
                # This shouldn't happen
                print(
                    f"Error - could not lock lockfile {self._lockfile.name}:",
                    exception,
                )
            else:
                return True
        return False

    def unlock(self) -> None:
        """Unlock and close lockfile."""
        if self._lockfile:
            try:
                self._lockfile.close()
            except OSError as exception:
                # This shouldn't happen
                print(
                    f"Error - could not close lockfile {self._lockfile.name}:",
                    exception,
                )
        if self._lock:
            try:
                self._lock.unlock()
            except UnlockingError as exception:
                # This shouldn't happen
                print(
                    f"Warning - could not unlock lockfile {self._lockfile.name}:",
                    exception,
                )

    def write(self, contents: str) -> None:
        """Write contents to lockfile.

        Args:
            contents (str): Contents to write.
        """
        if self._lockfile:
            try:
                self._lockfile.write(f"{contents}\n")
            except OSError as exception:
                # This shouldn't happen
                print(
                    f"Error - could not write to lockfile {self._lockfile.name}:",
                    exception,
                )


class AppSocket:
    """Socket wrapper class."""

    def __init__(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as exception:
            # This shouldn't happen
            print("Warning - could not create TCP socket:", exception)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Return attribute of socket.

        Args:
            name (str): Attribute name.

        Returns:
            Any: Attribute of socket.
        """
        return getattr(self.socket, name)

    def __bool__(self) -> bool:
        """Return True if socket was successfully created.

        Returns:
            bool: True if socket was successfully created, False otherwise.
        """
        return hasattr(self, "socket")

    def connect(self, host: str, port: int) -> bool:
        """Connect to host:port.

        Args:
            host (str): Host to connect to.
            port (int): Port to connect to.

        Returns:
            bool: True on success, False on failure.
        """
        try:
            self.socket.connect((host, port))
        except OSError as exception:
            # Other instance probably died
            print(f"Connection to {host}:{port} failed:", exception)
            return False
        return True

    def read(self) -> str:
        """Read data until EOT character (ASCII 4) is found.

        Returns:
            str: Incoming data.
        """
        incoming = ""
        while "\4" not in incoming:
            try:
                data = self.socket.recv(1024).decode("utf-8")
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                print("Warning - could not receive data:", exception)
                break
            if not data:
                break
            incoming += data
        return incoming

    def send(self, data: str) -> bool:
        """Send data.

        Args:
            data (str): Data to send.

        Returns:
            bool: True on success, False on failure.
        """
        print("AppSocket.send start")
        try:
            # self.socket.send(("%s\n" % data).encode())
            data_to_send = f"{data}\n".encode()
            print(f"data_to_send: {data_to_send}")
            self.socket.sendall(data_to_send)
        except OSError as exception:
            # Connection lost?
            print(f"Warning - could not send data {data!r}:", exception)
            return False
        return True


class Error(Exception):
    """Generic error class."""


if __name__ == "__main__":
    main()
