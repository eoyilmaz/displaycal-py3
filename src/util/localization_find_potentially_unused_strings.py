#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import jsondict
from DisplayCAL.config import confighome
from DisplayCAL.util_os import listdir_re


def quote(obj):
    if isinstance(obj, str):
        return '"%s"' % obj.replace("\\", "\\\\").replace('"', '\\"').replace(
            "\n", "\\n"
        )
    else:
        return repr(obj)


def find_potentially_unused_strings(filepath, keys):
    ldict = jsondict.JSONDict(filepath)

    merged = dict()
    merged["*"] = ""

    count = 0
    for key in sorted(ldict.keys()):
        merged[key.encode("UTF-8")] = ldict[key].encode("UTF-8")
        if not key.startswith("*") and not key.startswith("!") and key not in keys:
            print(
                "Found potentially unused '%s' in '%s'"
                % (key, os.path.basename(filepath))
            )
            count += 1
    print(
        "Found %i potentially unused keys in '%s'" % (count, os.path.basename(filepath))
    )


def main():
    keys = {}
    for (dirpath, _dirnames, filenames) in os.walk(os.path.join(root, "DisplayCAL")):
        for filename in filenames:
            ext = os.path.splitext(filename)[1][1:]
            if ext not in ("py", "pyw", "xrc"):
                continue
            filepath = os.path.join(dirpath, filename)
            with open(filepath, "rb") as py:
                code = py.read().decode()
            if ext == "xrc":
                pattern = r"<(?:label|title|tooltip)>([^>]+)</(?:label|title|tooltip)>"
            else:
                pattern = r'(?:getstr\(|(?:lstr|msg|msgid|msgstr|title)\s*=)\s*["\']([^"\']+)["\']'
            for match in re.findall(pattern, code):
                if match not in keys:
                    keys[match.decode("UTF-8")] = 1
    print(len(keys), "unique keys in py/pyw/xrc")
    usage_path = os.path.join(confighome, "localization_usage.json")
    if os.path.isfile(usage_path):
        usage = jsondict.JSONDict(usage_path)
        usage.load()
        keys.update(usage)
        print(len(keys), "unique keys after merging localization_usage.json")
    for langfile in listdir_re(
        os.path.join(root, "DisplayCAL", "lang"), r"^\w+\.json$"
    ):
        if langfile != "en.json":
            find_potentially_unused_strings(os.path.join("lang", langfile), keys.keys())
            input("Press any key to continue")
            print("")


if __name__ == "__main__":
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print("Usage: %s" % os.path.basename(sys.argv[0]))
        print("Finds potentially unused strings in localizations")
    else:
        main()
