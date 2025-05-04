#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wx
from wx.lib.agw import floatspin

from DisplayCAL import colormath as cm
import importlib

app = wx.GetApp() or wx.App(0)
f = wx.Frame(
    None,
    -1,
    "BT.2390 Test",
    style=wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER & ~wx.MAXIMIZE_BOX,
)
p = wx.Panel(f)
s = wx.FlexGridSizer(0, 2, 10, 10)
p.Sizer = s
rb = wx.Button(p, -1, "Reload colormath module")
rb.Bind(wx.EVT_BUTTON, lambda e: importlib.reload(cm))
ml = floatspin.FloatSpin(
    p,
    -1,
    min_val=0.0,
    max_val=10000.0,
    value=0.0,
    increment=0.0001,
    digits=4,
    agwStyle=floatspin.FS_RIGHT,
)
oo = wx.Slider(
    p, -1, 0, 0, 100, size=(100, -1), style=wx.SL_HORIZONTAL | wx.SL_VALUE_LABEL
)
xl = floatspin.FloatSpin(
    p,
    -1,
    min_val=100.0,
    max_val=10000.0,
    value=10000.0,
    increment=0.1,
    digits=1,
    agwStyle=floatspin.FS_RIGHT,
)
lb = floatspin.FloatSpin(
    p,
    -1,
    min_val=0.0,
    max_val=10000.0,
    value=0.0,
    increment=0.0001,
    digits=4,
    agwStyle=floatspin.FS_RIGHT,
)
lw = floatspin.FloatSpin(
    p,
    -1,
    min_val=100.0,
    max_val=10000.0,
    value=10000.0,
    increment=0.1,
    digits=1,
    agwStyle=floatspin.FS_RIGHT,
)
cb = wx.Button(p, -1, "Copy BT.2390 values")


def bt2390_test(event):
    try:
        outo = oo.Value / 100.0  # Output offset
        minLum = ml.GetValue()
        maxLum = xl.GetValue()
        LB = lb.GetValue()
        LW = lw.GetValue()
        bt2390 = cm.BT2390(minLum * (1 - outo), maxLum, LB, LW)
        maxLum = cm.specialpow(bt2390.apply(1), -2084) * 10000
        txt = ""
        for i in range(1024):
            txt += "%f\n" % cm.convert_range(
                cm.specialpow(bt2390.apply(i / 1023.0), -2084) * 10000,
                0,
                maxLum,
                minLum * outo,
                maxLum,
            )
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(txt))
            wx.TheClipboard.Close()
        else:
            wx.MessageDialog(
                f, "Could not open clipboard!", "Clipboard error", style=wx.OK
            ).ShowModal()
    except Exception:
        wx.MessageDialog(
            f, traceback.format_exc(), "Exception", style=wx.OK
        ).ShowModal()


cb.Bind(wx.EVT_BUTTON, bt2390_test)


s.Add((0, 0))
s.Add(rb, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.RIGHT | wx.TOP, border=10)
s.Add(
    wx.StaticText(p, -1, "Target display minimum black luminance cd/m²"),
    flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
    border=10,
)
s.Add(ml, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
s.Add(
    wx.StaticText(p, -1, "Output offset %"),
    flag=wx.ALIGN_RIGHT | wx.ALIGN_BOTTOM | wx.LEFT,
    border=10,
)
s.Add(oo, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND | wx.RIGHT, border=10)
s.Add(
    wx.StaticText(p, -1, "Target display peak white luminance cd/m²"),
    flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
    border=10,
)
s.Add(xl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
s.Add(
    wx.StaticText(p, -1, "Mastering display minimum black luminance cd/m²"),
    flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
    border=10,
)
s.Add(lb, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
s.Add(
    wx.StaticText(p, -1, "Mastering display peak white luminance cd/m²"),
    flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
    border=10,
)
s.Add(lw, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
s.Add((0, 0))
s.Add(cb, flag=wx.EXPAND | wx.RIGHT | wx.BOTTOM, border=10)
s.SetSizeHints(f)
s.Layout()
f.Show()
app.MainLoop()
