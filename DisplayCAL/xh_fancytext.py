"""This module provides a custom XML resource handler for wxPython to create
and manage StaticFancyText controls from XML resource files. It allows
configuration of properties such as label text, position, size, and styles.
"""

from wx import xrc

from DisplayCAL.log import safe_print

try:
    from DisplayCAL.wx_windows import BetterStaticFancyText as StaticFancyText
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
