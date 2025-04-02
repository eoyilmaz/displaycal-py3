#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import jsondict
from DisplayCAL.util_list import natsort
from DisplayCAL.util_os import safe_glob


def convert(infilename):
    dictin = jsondict.JSONDict(infilename)
    dictin.load()

    outfilename = os.path.splitext(infilename)[0] + ".yaml"
    with open(outfilename, "wb") as outfile:
        for key in natsort(dictin.keys(), False):
            outfile.write('"%s": |-\n' % key.encode("UTF-8"))
            for line in dictin[key].split("\n"):
                # Do not use splitlines, returns empty list for empty string
                outfile.write("  %s\n" % line.encode("UTF-8"))


if __name__ == "__main__":
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print("Usage: %s" % os.path.basename(sys.argv[0]))
        print("Converts translation JSON files to YAML files")
    else:
        for langfile in safe_glob(os.path.join(root, "DisplayCAL", "lang", "*.json")):
            convert(langfile)
