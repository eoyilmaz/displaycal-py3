#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL.defaultpaths import ICCPROFILES, ICCPROFILES_HOME

for p in set(ICCPROFILES_HOME + ICCPROFILES):
    if os.path.isdir(p):
        for f in os.listdir(p):
            try:
                profile = iccp.ICCProfile(os.path.join(p, f))
            except Exception:
                pass
            else:
                if profile.creator == b"argl":
                    print(f)
                    print("")
