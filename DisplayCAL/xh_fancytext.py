"""
xh_fancytext.py — XRC handler for StaticFancyText controls.

This module defines a custom XmlResourceHandler for integrating
StaticFancyText widgets into wxPython XRC resource files. StaticFancyText is
a label-like control that can render styled text with simple markup, such as
bold or italic spans.

When declared in an XRC file with <object class="StaticFancyText">, this
handler creates and configures the control, applying properties such as the
text label, position, size, and style. If the widget is marked as hidden in
XRC, it is automatically hidden after creation.
"""

import wx.xrc as xrc
from DisplayCAL.log import safe_print

try:
    from DisplayCAL.wxwindows import BetterStaticFancyText as StaticFancyText
except ImportError:
    from wx.lib.fancytext import StaticFancyText


class StaticFancyTextCtrlXmlHandler(xrc.XmlResourceHandler):
    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, "StaticFancyText")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        try:
            text = self.GetText("label")
        except Exception:
            text = ""
        w = StaticFancyText(
            self.GetParentAsWindow(),
            self.GetID(),
            text,
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
