# -*- coding: utf-8 -*-

import sys


def get_encoding(stream):
    """Return stream encoding."""
    return sys.getdefaultencoding()  # which is "utf-8" for all OSes after Python 3.6


def get_encodings():
    """Return console encoding, filesystem encoding."""
    enc = get_encoding(sys.stdout)  # this is "utf-8" for all OSes
    fs_enc = sys.getfilesystemencoding() or enc  # this is "utf-8" for all OSes
    return enc, fs_enc
