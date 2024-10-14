# -*- coding: utf-8 -*-

import ctypes
from ctypes import wintypes

# Constants for taskbar progress states
TBPF_NOPROGRESS = 0
TBPF_INDETERMINATE = 0x1
TBPF_NORMAL = 0x2
TBPF_ERROR = 0x4
TBPF_PAUSED = 0x8


# Define the ITaskbarList3 interface
class ITaskbarList3(ctypes.Structure):
    _fields_ = [
        ("SetProgressValue", ctypes.c_void_p),
        ("SetProgressState", ctypes.c_void_p),
        # Add other methods if needed
    ]


# Load the Shell32.dll and get the ITaskbarList3 interface
shell32 = ctypes.windll.shell32

ITaskbarList3_ptr = ctypes.POINTER(ITaskbarList3)
CoCreateInstance = ctypes.windll.ole32.CoCreateInstance
CLSID_TaskbarList = ctypes.c_char_p(b"{56FDF344-FD6D-11d0-958A-006097C9A090}")
IID_ITaskbarList3 = ctypes.c_char_p(b"{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}")


class Taskbar(object):
    def __init__(self, frame, maxv=100):
        self.frame = frame
        self.maxv = maxv
        self.taskbar = self._create_taskbar_instance()

    def _create_taskbar_instance(self):
        taskbar = ITaskbarList3_ptr()
        hr = CoCreateInstance(
            ctypes.byref(ctypes.c_void_p(CLSID_TaskbarList)),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_ITaskbarList3),
            ctypes.byref(taskbar),
        )
        if hr != 0:
            raise ctypes.WinError(hr)
        return taskbar

    def set_progress_value(self, value):
        if self.frame:
            hwnd = self.frame.GetHandle()
            self.taskbar.contents.SetProgressValue(hwnd, value, self.maxv)

    def set_progress_state(self, state):
        if self.frame:
            hwnd = self.frame.GetHandle()
            self.taskbar.contents.SetProgressState(hwnd, state)
