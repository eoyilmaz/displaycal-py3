# -*- coding: utf-8 -*-

import os
import warnings


def get_display(display_name=None):
    """Parse X display name and return (hostname, display number, screen number)"""
    if not display_name:
        display_name = (os.getenv("DISPLAY", ":0.0")).encode("utf-8")
    display_parts = display_name.split(b":")
    hostname = display_parts[0].decode()
    display, screen = 0, 0
    if len(display_parts) > 1:
        try:
            display_screen = tuple(int(n) for n in display_parts[1].split(b"."))
        except ValueError:
            warnings.warn(
                f"invalid value for display name: '{display_name.decode()}'",
                Warning,
            )
        else:
            display = display_screen[0]
            if len(display_screen) > 1:
                screen = display_screen[1]
            else:
                screen = 0
    return hostname, display, screen
