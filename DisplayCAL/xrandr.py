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
    def __init__(self, name=None):
        self.name = name or os.getenv("DISPLAY")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, etype, value, tb):
        self.close()

    def open(self):
        self.display = libx11.XOpenDisplay(self.name.encode())
        if not self.display:
            raise ValueError(f"Invalid X display {self.name!r}")

    def close(self):
        libx11.XCloseDisplay(self.display)

    def intern_atom(self, atom_name):
        atom_id = libx11.XInternAtom(self.display, atom_name, False)
        if not atom_id:
            raise ValueError(f"Invalid atom name {atom_name!r}")

        return atom_id

    def root_window(self, screen_no=0):
        window = libx11.XRootWindow(self.display, screen_no)
        if not window:
            raise ValueError(f"Invalid X screen {screen_no!r}")

        return window

    def get_window_property(self, window, atom_id, atom_type=XA_CARDINAL):
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
