# -*- coding: utf-8 -*-

import win32com.client

TBPF_NOPROGRESS = 0
TBPF_INDETERMINATE = 0x1
TBPF_NORMAL = 0x2
TBPF_ERROR = 0x4
TBPF_PAUSED = 0x8

try:
    taskbar = win32com.client.Dispatch("Shell.Taskbar")
except Exception as e:
    print(f"Error creating COM object: {e}")

class Taskbar(object):
    def __init__(self, frame, maxv=100):
        self.frame = frame
        self.maxv = maxv

    def set_progress_value(self, value):
        if self.frame:
            taskbar.SetProgressValue(self.frame.GetHandle(), value, self.maxv)

    def set_progress_state(self, state):
        if self.frame:
            taskbar.SetProgressState(self.frame.GetHandle(), state)
