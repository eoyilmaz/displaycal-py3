"""Provides the `PyEmbeddedImage` class for embedding PNG image data in Python code.

It is primarily used with the `wx.tools.img2py` code generator to simplify the
distribution of image assets by embedding them as base64-encoded data within
Python modules.
"""
# ----------------------------------------------------------------------
# Name:        wx.lib.embeddedimage
# Purpose:     Defines a class used for embedding PNG images in Python
#              code. The primary method of using this module is via
#              the code generator in wx.tools.img2py.
#
# Author:      Anthony Tuininga
#
# Created:     26-Nov-2007
# RCS-ID:      $Id: embeddedimage.py 59672 2009-03-20 20:59:42Z RD $
# Copyright:   (c) 2007 by Anthony Tuininga
# Licence:     wxWindows license
# ----------------------------------------------------------------------

import base64
import io

import wx

try:
    b64decode = base64.b64decode
except AttributeError:
    b64decode = base64.decodestring


class PyEmbeddedImage:
    """A class for embedding PNG images in Python code.

    PyEmbeddedImage is primarily intended to be used by code generated
    by img2py as a means of embedding image data in a python module so
    the image can be used at runtime without needing to access the
    image from an image file.  This makes distributing icons and such
    that an application uses simpler since tools like py2exe will
    automatically bundle modules that are imported, and the
    application doesn't have to worry about how to locate the image
    files on the user's filesystem.

    The class can also be used for image data that may be acquired
    from some other source at runtime, such as over the network or
    from a database.  In this case pass False for isBase64 (unless the
    data actually is base64 encoded.)  Any image type that
    wx.ImageFromStream can handle should be okay.
    """

    def __init__(self, data, isBase64=True):
        self.data = data
        self.isBase64 = isBase64

    def GetBitmap(self):
        """Return a wx.Bitmap object created from the embedded image data.

        Returns:
            wx.Bitmap: The bitmap created from the embedded data.
        """
        return wx.BitmapFromImage(self.GetImage())

    def GetData(self):
        """Return the raw image data, decoding it if necessary.

        Returns:
            bytes: The raw image data, decoded if it was base64 encoded.
        """
        if self.isBase64:
            data = b64decode(self.data)
        # TODO: what is ``data`` if self.isBase64 is False
        return data

    def GetIcon(self):
        """Return a wx.Icon object created from the embedded image data.

        Returns:
            wx.Icon: The icon created from the embedded data.
        """
        icon = wx.EmptyIcon()
        icon.CopyFromBitmap(self.GetBitmap())
        return icon

    def GetImage(self):
        """Return a wx.Image object created from the embedded image data.

        Returns:
            wx.Image: The image created from the embedded data.
        """
        stream = io.BytesIO(self.GetData())
        return wx.ImageFromStream(stream)

    # define properties, for convenience
    Bitmap = property(GetBitmap)
    Icon = property(GetIcon)
    Image = property(GetImage)
