#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home


def main():
    for p in set(iccprofiles_home + iccprofiles):
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            try:
                profile = iccp.ICCProfile(os.path.join(p, f))
            except Exception:
                pass
            if not "clrt" in profile.tags:
                continue
            print(f)
            print(profile.connectionColorSpace)
            for name in profile.tags.clrt:
                print(name, profile.tags.clrt[name])
            print("")


if __name__ == "__main__":
    main()
