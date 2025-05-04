#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

from PIL import Image


def find_iCCP_pngs():
    for (dirpath, _dirnames, filenames) in os.walk(
        os.path.join(os.path.dirname(__file__), "..", "DisplayCAL")
    ):
        for filename in filenames:
            if filename.lower().endswith(".png"):
                filepath = os.path.join(dirpath, filename)
                png = Image.open(filepath)
                if "icc_profile" in png.info:
                    print(filepath)


if __name__ == "__main__":
    find_iCCP_pngs()
