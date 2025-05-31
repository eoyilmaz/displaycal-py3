"""X11/Xrandr ctypes interface.

It allows querying and manipulating X display properties, including retrieving
window and output properties. The module is useful for working with X server
configurations and display outputs programmatically.
"""

from __future__ import annotations

import os
import sys
from ctypes import (
    POINTER,
    Structure,
    c_int,
    c_long,
    c_ubyte,
    c_ulong,
    cdll,
    pointer,
    util,
)
from typing import ClassVar

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


libx11pth = util.find_library("X11")
if not libx11pth:
    raise ImportError("Couldn't find libX11")
try:
    libx11 = cdll.LoadLibrary(libx11pth)
except OSError as e:
    raise ImportError("Couldn't load libX11") from e

libxrandrpth = util.find_library("Xrandr")
if not libxrandrpth:
    raise ImportError("Couldn't find libXrandr")
try:
    libxrandr = cdll.LoadLibrary(libxrandrpth)
except OSError as e:
    raise ImportError("Couldn't load libXrandr") from e

from DisplayCAL.options import DEBUG

XA_CARDINAL = 6
XA_INTEGER = 19

Atom = c_ulong


class Display(Structure):
    """Structure representing an X display connection.

    This structure is used to manage the connection to the X server and
    perform operations on the display.
    """

    __slots__ = []
    _fields_: ClassVar[list[tuple]] = [("_opaque_struct", c_int)]


try:
    libx11.XInternAtom.restype = Atom
    libx11.XOpenDisplay.restype = POINTER(Display)
    libx11.XRootWindow.restype = c_ulong
    libx11.XGetWindowProperty.restype = c_int
    libx11.XGetWindowProperty.argtypes = [
        POINTER(Display),
        c_ulong,
        Atom,
        c_long,
        c_long,
        c_int,
        c_ulong,
        POINTER(c_ulong),
        POINTER(c_int),
        POINTER(c_ulong),
        POINTER(c_ulong),
        POINTER(POINTER(c_ubyte)),
    ]
except AttributeError as exception:
    raise ImportError(f"libX11: {exception}") from exception

try:
    libxrandr.XRRGetOutputProperty.restype = c_int
    libxrandr.XRRGetOutputProperty.argtypes = [
        POINTER(Display),
        c_ulong,
        Atom,
        c_long,
        c_long,
        c_int,
        c_int,
        c_ulong,
        POINTER(c_ulong),
        POINTER(c_int),
        POINTER(c_ulong),
        POINTER(c_ulong),
        POINTER(POINTER(c_ubyte)),
    ]
except AttributeError as exception:
    raise ImportError(f"libXrandr: {exception}") from exception


class XDisplay:
    """Class to manage an X display connection and perform operations on it.

    Args:
        name (str | None): The name of the display to connect to. If None, it
            will use the DISPLAY environment variable. Defaults to None.
    """

    def __init__(self, name=None):
        self.name = name or os.getenv("DISPLAY")

    def __enter__(self) -> Self:
        """Enter the runtime context related to this object."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        """Exit the runtime context related to this object.

        Args:
            exc_type: The exception type.
            exc_value: The exception value.
            tb: The traceback object.
        """
        self.close()

    def open(self) -> None:
        """Open a connection to the X display.

        Raises:
            ValueError: If the display name is invalid or cannot be opened.
        """
        self.display = libx11.XOpenDisplay(self.name.encode())
        if not self.display:
            raise ValueError(f"Invalid X display {self.name!r}")

    def close(self) -> None:
        """Close the X display connection."""
        libx11.XCloseDisplay(self.display)

    def intern_atom(self, atom_name):
        """Intern an atom by its name.

        Args:
            atom_name (str): The name of the atom to intern.

        Raises:
            ValueError: If the atom name is invalid or cannot be interned.

        Returns:
            int: The atom identifier for the specified atom name.
        """
        atom_id = libx11.XInternAtom(self.display, atom_name, False)
        if not atom_id:
            raise ValueError(f"Invalid atom name {atom_name!r}")

        return atom_id

    def root_window(self, screen_no=0):
        """Get the root window for a given screen number.

        Args:
            screen_no (int): The screen number for which to get the root window.
                Defaults to 0.

        Raises:
            ValueError: If the screen number is invalid or the root window cannot
                be retrieved.

        Returns:
            int: The root window identifier for the specified screen.
        """
        window = libx11.XRootWindow(self.display, screen_no)
        if not window:
            raise ValueError(f"Invalid X screen {screen_no!r}")

        return window

    def get_window_property(self, window, atom_id, atom_type=XA_CARDINAL):
        """Get the property of an X window.

        Args:
            window (int): The window identifier.
            atom_id (int): The atom identifier for the property.
            atom_type (int): The type of the atom, default is XA_CARDINAL.

        Raises:
            ValueError: If the window is invalid or the property cannot be retrieved.

        Returns:
            list: A list of property values for the specified window.
        """
        ret_type, ret_format, ret_len, ret_togo, atomv = (
            c_ulong(),
            c_int(),
            c_ulong(),
            c_ulong(),
            pointer(c_ubyte()),
        )

        window_property = None
        if (
            libx11.XGetWindowProperty(
                self.display,
                window,
                atom_id,
                0,
                0x7FFFFFF,
                False,
                atom_type,
                ret_type,
                ret_format,
                ret_len,
                ret_togo,
                atomv,
            )
            == 0
            and ret_len.value > 0
        ):
            if DEBUG:
                print("ret_type:", ret_type.value)
                print("ret_format:", ret_format.value)
                print("ret_len:", ret_len.value)
                print("ret_togo:", ret_togo.value)
            window_property = [atomv[i] for i in range(ret_len.value)]

        return window_property

    def get_output_property(self, output, atom_id, atom_type=XA_CARDINAL):
        """Get the property of an X output.

        Args:
            output (int): The output identifier.
            atom_id (int): The atom identifier for the property.
            atom_type (int): The type of the atom, default is XA_CARDINAL.

        Raises:
            ValueError: If the output is invalid or the property cannot be retrieved.

        Returns:
            list: A list of property values for the specified output.
        """
        if not output:
            raise ValueError(f"Invalid output {output!r} specified")

        ret_type, ret_format, ret_len, ret_togo, atomv = (
            c_ulong(),
            c_int(),
            c_ulong(),
            c_ulong(),
            pointer(c_ubyte()),
        )

        output_property = None
        if (
            libxrandr.XRRGetOutputProperty(
                self.display,
                output,
                atom_id,
                0,
                0x7FFFFFF,
                False,
                False,
                atom_type,
                ret_type,
                ret_format,
                ret_len,
                ret_togo,
                atomv,
            )
            == 0
            and ret_len.value > 0
        ):
            if DEBUG:
                print("ret_type:", ret_type.value)
                print("ret_format:", ret_format.value)
                print("ret_len:", ret_len.value)
                print("ret_togo:", ret_togo.value)
            output_property = [atomv[i] for i in range(ret_len.value)]

        return output_property


if __name__ == "__main__":
    with XDisplay() as display:
        output_property = display.get_output_property(
            int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
        )
        print(f"{sys.argv[2]} for display {sys.argv[1]}: {output_property!r}")
