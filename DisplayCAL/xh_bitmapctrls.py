"""This module provides custom XML resource handlers for wxPython to create and
manage bitmap-based controls, such as wxBitmapButton and wxStaticBitmap,
from XML resource files. It includes functionality to process XML parameters,
load bitmaps, and configure the controls.
"""

import os

import wx
from wx import xrc

from DisplayCAL.config import getbitmap
from DisplayCAL.log import safe_print


class BitmapButton(xrc.XmlResourceHandler):
    """Custom XML resource handler for wxBitmapButton controls."""

    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, "wxBitmapButton")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        name = os.path.splitext(self.GetText("bitmap"))[0]
        if name.startswith("../"):
            name = name[3:]
        bitmap = getbitmap(name)
        w = wx.BitmapButton(
            self.GetParentAsWindow(),
            self.GetID(),
            bitmap,
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


class StaticBitmap(xrc.XmlResourceHandler):
    """Custom XML resource handler for wxStaticBitmap controls."""

    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, "wxStaticBitmap")

    # Process XML parameters and create the object
    def DoCreateResource(self):
        name = os.path.splitext(self.GetText("bitmap"))[0]
        if name.startswith("../"):
            name = name[3:]
        bitmap = getbitmap(name)
        w = wx.StaticBitmap(
            self.GetParentAsWindow(),
            self.GetID(),
            bitmap,
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
