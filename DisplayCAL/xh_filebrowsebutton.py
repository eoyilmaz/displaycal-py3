# -*- coding: utf-8 -*-

import wx
import wx.xrc as xrc
import wx.lib.filebrowsebutton as filebrowse
from DisplayCAL.log import safe_print

try:
    from DisplayCAL.wxwindows import (
        FileBrowseBitmapButtonWithChoiceHistory as FileBrowseButtonWithHistory,
    )
except ImportError:
    FileBrowseButtonWithHistory = filebrowse.FileBrowseButtonWithHistory


class FileBrowseButtonXmlHandler(xrc.XmlResourceHandler):
    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        self._class = filebrowse.FileBrowseButton
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        return self.IsOfClass(node, self._class.__name__)

    # Process XML parameters and create the object
    def DoCreateResource(self):
        w = self._class(
            parent=self.GetParentAsWindow(),
            id=self.GetID(),
            pos=self.GetPosition(),
            size=self.GetSize(),
            style=self.GetStyle(),
            labelText=self.GetText("message") or "File Entry:",
            buttonText=self.GetText("buttonText") or "Browse",
            toolTip=self.GetText("toolTip")
            or "Type filename or click browse to choose file",
            dialogTitle=self.GetText("dialogTitle") or "Choose a file",
            startDirectory=self.GetText("startDirectory") or ".",
            initialValue=self.GetText("initialValue") or "",
            fileMask=self.GetText("wildcard") or "*.*",
            fileMode=self.GetLong("fileMode") or wx.FD_OPEN,
            labelWidth=self.GetLong("labelWidth") or 0,
            name=self.GetName(),
        )
        self.SetupWindow(w)
        if self.GetBool("hidden") and w.Shown:
            safe_print(f"{self.Name} should have been hidden")
            w.Hide()
        return w


class FileBrowseButtonWithHistoryXmlHandler(FileBrowseButtonXmlHandler):
    def __init__(self):
        FileBrowseButtonXmlHandler.__init__(self)
        self._class = FileBrowseButtonWithHistory

    def CanHandle(self, node):
        return self.IsOfClass(node, self._class.__name__) or self.IsOfClass(
            node, "FileBrowseButtonWithHistory"
        )
