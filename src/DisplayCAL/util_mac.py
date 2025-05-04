# -*- coding: utf-8 -*-

import os
import re
import subprocess as sp
from time import sleep

from DisplayCAL.meta import name as appname
from DisplayCAL.options import verbose


def get_osascript_args(applescript):
    """Return arguments ready to use for osascript"""
    if isinstance(applescript, str):
        applescript = applescript.splitlines()
    args = []
    for line in applescript:
        args.extend(["-e", line])
    return args


def get_osascript_args_or_run(applescript, run=True):
    """Return arguments ready to use for osascript or run the AppleScript"""
    if run:
        return osascript(applescript)
    else:
        return get_osascript_args(applescript)


def mac_app_activate(delay=0, mac_app_name="Finder"):
    """Activate (show & bring to front) an application if it is running."""
    applescript = [
        'if app "%s" is running then' % mac_app_name,
        # Use 'run script' to prevent the app activating upon script
        # compilation even if not running
        r'run script "tell app \"%s\" to activate"' % mac_app_name,
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
                'do script "%s" in first window' % script.replace('"', '\\"'),
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
        'set background color of first window to "%s"' % background,
        'set cursor color of first window to "%s"' % cursor,
        'set normal text color of first window to "%s"' % text,
        'set bold text color of first window to "%s"' % text_bold,
        "end tell",
    ]
    return get_osascript_args_or_run(applescript, do)


def osascript(applescript):
    """Run AppleScript with the 'osascript' command

    Return osascript's exit code.

    """
    args = get_osascript_args(applescript)
    p = sp.Popen(["osascript"] + args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    output, errors = p.communicate()
    retcode = p.wait()
    return retcode, output, errors


def get_model_code(serial=None):
    """Given a mac serial number, return the model code

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
    """Return this mac's serial number"""
    try:
        p = sp.Popen(
            ["ioreg", "-c", "IOPlatformExpertDevice", "-d", "2"],
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


def get_model_id():
    """Return this mac's model id"""
    try:
        p = sp.Popen(
            ["sysctl", "hw.model"], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
        )
        output, errors = p.communicate()
    except BaseException:
        return None
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    return "".join(output).split(None, 1)[-1].strip()


def get_machine_attributes(model_id=None):
    """Given a mac model ID, return the machine attributes

    If model_code is None, this mac's model code is used.

    """
    if not model_id:
        model_id = get_model_id()
        if not model_id:
            return None
    pf = "/System/Library/PrivateFrameworks"
    f = ".framework/Versions/A/Resources/English.lproj"
    sk = "%s/ServerKit%s/XSMachineAttributes" % (pf, f)
    si = "%s/ServerInformation%s/SIMachineAttributes" % (pf, f)
    if os.path.isfile(si + ".plist"):
        # Mac OS X 10.8 or newer
        filename = si
    else:
        # Mac OS X 10.6/10.7
        filename = sk
    try:
        p = sp.Popen(
            ["defaults", "read", filename, model_id],
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
            attrs[match.group(1)] = (
                match.group(2).decode("string_escape").decode("string_escape")
            )
    return attrs
