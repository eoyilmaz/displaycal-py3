"""macOS utility functions for AppleScript, system info, and Terminal settings."""

import codecs
import ctypes
import os
import re
import subprocess as sp
import sys
from time import sleep


def get_osascript_args(applescript):
    """Return arguments ready to use for osascript."""
    if isinstance(applescript, str):
        applescript = applescript.splitlines()
    args = []
    for line in applescript:
        args.extend(["-e", line])
    return args


def get_osascript_args_or_run(applescript, run=True):
    """Return arguments ready to use for osascript or run the AppleScript."""
    if run:
        return osascript(applescript)
    return get_osascript_args(applescript)


def mac_app_activate(delay=0, mac_app_name="Finder"):
    """Activate (show & bring to front) an application if it is running."""
    applescript = [
        f'if app "{mac_app_name}" is running then',
        # Use 'run script' to prevent the app activating upon script
        # compilation even if not running
        rf'run script "tell app \"{mac_app_name}\" to activate"',
        "end if",
    ]
    if delay:
        sleep(delay)
    return osascript(applescript)


def mac_terminal_do_script(script=None, do=True):
    """Run a script in Terminal."""
    applescript = [
        'if app "Terminal" is running then',
        'tell app "Terminal"',
        "activate",
        'do script ""',  # Terminal is already running, open a new
        # window to make sure it is not blocked by
        # another process
        "end tell",
        "else",
        'tell app "Terminal" to activate',  # Terminal is not yet running,
        # launch & use first window
        "end if",
    ]
    if script:
        applescript.extend(
            [
                'tell app "Terminal"',
                'do script "{}" in first window'.format(script.replace('"', '\\"')),
                "end tell",
            ]
        )
    return get_osascript_args_or_run(applescript, script and do)


def mac_terminal_set_colors(
    background="black", cursor="gray", text="gray", text_bold="gray", do=True
):
    """Set Terminal colors."""
    applescript = [
        'tell app "Terminal"',
        f'set background color of first window to "{background}"',
        f'set cursor color of first window to "{cursor}"',
        f'set normal text color of first window to "{text}"',
        f'set bold text color of first window to "{text_bold}"',
        "end tell",
    ]
    return get_osascript_args_or_run(applescript, do)


def osascript(applescript):
    """Run AppleScript with the 'osascript' command.

    Return osascript's exit code.

    """
    args = get_osascript_args(applescript)
    p = sp.Popen(
        ["osascript", *args],  # noqa: S607
        stdin=sp.PIPE,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
    )
    output, errors = p.communicate()
    retcode = p.wait()
    return retcode, output, errors


def get_model_code(serial=None):
    """Given a mac serial number, return the model code.

    If serial is None, this mac's serial number is used.

    """
    if not serial:
        serial = get_serial()
    if serial:
        if "serial" in serial.lower():
            # Workaround for machines with dummy serial numbers
            return None
        if len(serial) in (12, 13) and serial.startswith("S"):
            # Remove prefix from scanned codes
            serial = serial[1:]
        if len(serial) in (11, 12):
            return serial[8:]
    return None


def get_serial():
    """Return this mac's serial number."""
    try:
        p = sp.Popen(
            ["ioreg", "-c", "IOPlatformExpertDevice", "-d", "2"],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        output, errors = p.communicate()
    except Exception:
        return None
    match = re.search(r'"IOPlatformSerialNumber"\s*=\s*"([^"]*)"', output.decode())
    if match:
        return match.group(1)
    return None


def get_model_id():
    """Return this mac's model id."""
    try:
        p = sp.Popen(
            ["sysctl", "hw.model"],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        output, errors = p.communicate()
    except BaseException:
        return None
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    return "".join(output).split(None, 1)[-1].strip()


def get_machine_attributes(model_id=None):
    """Given a mac model ID, return the machine attributes.

    If model_code is None, this mac's model code is used.

    """
    if not model_id:
        model_id = get_model_id()
        if not model_id:
            return None
    pf = "/System/Library/PrivateFrameworks"
    f = ".framework/Versions/A/Resources/English.lproj"
    sk = f"{pf}/ServerKit{f}/XSMachineAttributes"
    si = f"{pf}/ServerInformation{f}/SIMachineAttributes"
    # Mac OS X 10.8 or newer use "ServerInformation",
    # Mac OS X 10.6/10.7 "ServerKit"
    filename = si if os.path.isfile(f"{si}.plist") else sk
    try:
        p = sp.Popen(
            ["defaults", "read", filename, model_id],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        output, errors = p.communicate()
    except Exception:
        return None
    attrs = {}
    for line in output.splitlines():
        match = re.search(r'(\w+)\s*=\s*"?(.*?)"?\s*;', line.decode())
        if match:
            # Need to double unescape backslashes
            attrs[match.group(1)] = codecs.decode(
                codecs.decode(match.group(2), "unicode_escape"), "unicode_escape"
            )
    return attrs


_objc = None


def _get_objc():
    """Return the Objective-C runtime with typed functions (macOS), or None."""
    global _objc
    if _objc is None and sys.platform == "darwin":
        try:
            objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        except OSError:
            _objc = False
        else:
            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]
            objc.object_getClassName.restype = ctypes.c_char_p
            objc.object_getClassName.argtypes = [ctypes.c_void_p]
            _objc = objc
    return _objc or None


def _send(receiver, selector, *args):
    """Send an Objective-C message returning an object (or nothing)."""
    objc = _get_objc()
    prototype = ctypes.CFUNCTYPE(
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        *[ctypes.c_void_p] * len(args),
    )
    send = prototype(("objc_msgSend", objc))
    return send(receiver, objc.sel_registerName(selector), *args)


def _shared_application():
    """Return NSApp (created if need be), None off macOS."""
    objc = _get_objc()
    if objc is None:
        return None
    return _send(objc.objc_getClass(b"NSApplication"), b"sharedApplication")


def app_delegate():
    """Return the application's delegate (an object pointer), None if none."""
    app = _shared_application()
    return _send(app, b"delegate") if app else None


def set_app_delegate(delegate):
    """Make ``delegate`` (from :func:`app_delegate`) the application's again."""
    app = _shared_application()
    if app:
        _send(app, b"setDelegate:", delegate)


def app_delegate_class():
    """Return the class name of the application's delegate, None if none."""
    delegate = app_delegate()
    if not delegate:
        return None
    return _get_objc().object_getClassName(delegate).decode()
