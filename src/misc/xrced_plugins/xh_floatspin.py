# -*- coding: utf-8 -*-

import wx
import wx.xrc as xrc

try:
    import wx.lib.agw.floatspin as floatspin
except ImportError:
    from DisplayCAL import floatspin


class FloatSpinCtrlXmlHandler(xrc.XmlResourceHandler):
    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()
        # Custom styles
        self.AddStyle("FS_LEFT", floatspin.FS_LEFT)
        self.AddStyle("FS_RIGHT", floatspin.FS_RIGHT)
        self.AddStyle("FS_CENTRE", floatspin.FS_CENTRE)
        self.AddStyle("FS_READONLY", floatspin.FS_READONLY)

    def CanHandle(self, node):
        return self.IsOfClass(node, "FloatSpin")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        try:
            min_val = float(self.GetText("min_val"))
        except:
            min_val = None
        try:
            max_val = float(self.GetText("max_val"))
        except:
            max_val = None
        try:
            increment = float(self.GetText("increment"))
        except:
            increment = 1.0
        w = floatspin.FloatSpin(
            parent=self.GetParentAsWindow(),
            id=self.GetID(),
            pos=self.GetPosition(),
            size=self.GetSize(),
            style=self.GetStyle(),
            min_val=min_val,
            max_val=max_val,
            increment=increment,
            name=self.GetName(),
        )

        try:
            w.SetValue(float(self.GetText("value")))
        except:
            w.SetValue(0.0)

        try:
            w.SetDigits(int(self.GetText("digits")))
        except:
            pass

        self.SetupWindow(w)
        if self.GetBool("hidden") and w.Shown:
            print(f"{self.Name} should have been hidden")
            w.Hide()
        return w
