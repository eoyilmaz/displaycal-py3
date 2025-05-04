#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import wx


def main():
    img = wx.Image(640, 640)
    buf = img.GetDataBuffer()
    x = y = 0
    levels = []
    for i in range(256):
        for _j in range(5):
            levels.append(i)
    offset = 0
    for i, _byte in enumerate(buf):
        if i and i % 3 == 0:
            x += 1
            if x % 640 == 0:
                x = 0
                y += 1
                offset = y
            else:
                offset += 1
        level = levels[offset]
        buf[i] = chr(level)
    img.SaveFile(os.path.join(os.getcwd(), "gradient_8bit.png"), wx.BITMAP_TYPE_PNG)


if __name__ == "__main__":
    main()
