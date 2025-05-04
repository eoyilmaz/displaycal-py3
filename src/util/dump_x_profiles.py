#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import xrandr


def get_display(display=None):
    """Parse $DISPLAY and return (hostname, display number, screen number)"""
    display_parts = (display or os.getenv("DISPLAY", ":0.0")).split(":")
    hostname = display_parts[0]
    if len(display_parts) > 1:
        try:
            display_screen = tuple(int(n) for n in display_parts[1].split("."))
        except ValueError:
            raise ValueError("display has an unknown " "format: %r" % display)
        display = display_screen[0]
        if len(display_screen) > 1:
            screen = display_screen[1]
        else:
            screen = 0
    else:
        display, screen = 0, 0
    return hostname, display, screen


def main(display=None, display_no=0):
    x_hostname, x_display, x_screen = get_display(display)
    try:
        property = xrandr.get_output_property(
            display_no,
            "_ICC_PROFILE",
            xrandr.XA_CARDINAL,
            x_hostname,
            x_display,
            x_screen,
        )
    except ValueError as exception:
        print(exception)
    else:
        with open("XRROutputProperty._ICC_PROFILE.dump", "wb") as dump:
            dump.write("".join(chr(i) for i in property).encode())
            print("Created XRROutputProperty._ICC_PROFILE.dump")
    try:
        atom = xrandr.get_atom(
            "_ICC_PROFILE" + ("" if display_no == 0 else "_%s" % display_no),
            xrandr.XA_CARDINAL,
            x_hostname,
            x_display,
            x_screen,
        )
    except ValueError as exception:
        print(exception)
    else:
        with open("XAtom._ICC_PROFILE.dump", "wb") as dump:
            dump.write("".join(chr(i) for i in atom).encode())
            print("Created XAtom._ICC_PROFILE.dump")


if __name__ == "__main__":
    if "--help" in sys.argv[1:]:
        print("Usage: %s [ x_display [ display_no ] ... ]" % __file__)
    elif sys.argv[1:]:
        for arg in sys.argv[1:]:
            main(arg)
    else:
        main()
