#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home


for p in set(iccprofiles_home + iccprofiles):
    if os.path.isdir(p):
        for f in os.listdir(p):
            try:
                profile = iccp.ICCProfile(os.path.join(p, f))
            except Exception:
                pass
            else:
                if profile.profileClass == b"abst":
                    print(f)
                    print("ICC Version:", profile.version)
                    print("Color space:", profile.colorSpace)
                    print("Connection color space:", profile.connectionColorSpace)
                    print("")
