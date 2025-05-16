"""This module provides a custom XML resource handler for wxPython to create
and manage FloatSpin controls from XML resource files. It processes XML
parameters such as minimum/maximum values, increment, and initial value, and
configures the FloatSpin control accordingly.
"""

import contextlib

import wx
from wx import xrc

from DisplayCAL.log import safe_print

try:
    from DisplayCAL import floatspin
except ImportError:
    from wx.lib.agw import floatspin


class FloatSpinCtrlXmlHandler(xrc.XmlResourceHandler):
    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, "FloatSpin")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        try:
            min_val = float(self.GetText("min_val"))
        except Exception:
            min_val = None
        try:
            max_val = float(self.GetText("max_val"))
        except Exception:
            max_val = None
        try:
            increment = float(self.GetText("increment"))
        except Exception:
            increment = 1.0
        is_spinctrldbl = hasattr(wx, "SpinCtrlDouble") and issubclass(
            floatspin.FloatSpin, wx.SpinCtrlDouble
        )
        defaultstyle = wx.SP_ARROW_KEYS | wx.ALIGN_RIGHT if is_spinctrldbl else 0
        w = floatspin.FloatSpin(
            parent=self.GetParentAsWindow(),
            id=self.GetID(),
            pos=self.GetPosition(),
            size=self.GetSize(),
            style=self.GetStyle(defaults=defaultstyle),
            min_val=min_val,
            max_val=max_val,
            increment=increment,
            name=self.GetName(),
        )

        with contextlib.suppress(Exception):
            w.SetValue(float(self.GetText("value")))

        with contextlib.suppress(Exception):
            w.SetDigits(int(self.GetText("digits")))

        self.SetupWindow(w)
        if self.GetBool("hidden") and w.Shown:
            safe_print(f"{self.Name} should have been hidden")
            w.Hide()
        return w
