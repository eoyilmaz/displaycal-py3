"""This module provides a custom XML resource handler for wxPython to create
and manage HStretchStaticBitmap controls from XML resource files. It handles
the processing of XML parameters, creation of the control, and its
configuration.
"""

import wx
from wx import xrc

from DisplayCAL.log import safe_print

try:
    from DisplayCAL.wx_windows import HStretchStaticBitmap
except ImportError:
    HStretchStaticBitmap = wx.StaticBitmap


class HStretchStaticBitmapXmlHandler(xrc.XmlResourceHandler):
    """Custom XML resource handler for HStretchStaticBitmap controls."""

    def __init__(self):
        xrc.XmlResourceHandler.__init__(self)
        # Standard styles
        self.AddWindowStyles()

    def CanHandle(self, node):
        """Check if the node can be handled by this handler.

        Args:
            node (xrc.XmlNode): The XML node to check.

        Returns:
            bool: True if the node is of class HStretchStaticBitmap, False otherwise.
        """
        return self.IsOfClass(node, "HStretchStaticBitmap")

    # Process XML parameters and create the object
    def DoCreateResource(self) -> HStretchStaticBitmap:
        """Create the HStretchStaticBitmap control from XML parameters.

        Returns:
            HStretchStaticBitmap: The created HStretchStaticBitmap control.
        """
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
