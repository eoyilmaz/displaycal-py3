"""
xh_hstretchstatbmp.py — XRC handler for HStretchStaticBitmap widgets.

This module defines a custom XmlResourceHandler for integrating the
HStretchStaticBitmap widget into wxPython XRC-based user interfaces.
HStretchStaticBitmap behaves like a standard wx.StaticBitmap, but it is
capable of horizontally stretching its bitmap to fit the available space,
making it useful in responsive or resizable layouts.

When used in an XRC resource file, the <object class="HStretchStaticBitmap">
tag will be recognized and instantiated through this handler. If the
DisplayCAL-specific implementation is not available, it falls back to the
standard wx.StaticBitmap.
"""

import wx
import wx.xrc as xrc
from DisplayCAL.log import safe_print

try:
    from DisplayCAL.wxwindows import HStretchStaticBitmap
except ImportError:
    HStretchStaticBitmap = wx.StaticBitmap


class HStretchStaticBitmapXmlHandler(xrc.XmlResourceHandler):
    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, "HStretchStaticBitmap")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        w = HStretchStaticBitmap(
            self.GetParentAsWindow(),
            self.GetID(),
            self.GetBitmap("bitmap"),
            pos=self.GetPosition(),
            size=self.GetSize(),
            style=self.GetStyle(),
            name=self.GetName(),
        )

        self.SetupWindow(w)
        if self.GetBool("hidden") and w.Shown:
            safe_print(f"{self.Name} should have been hidden")
            w.Hide()
        return w
