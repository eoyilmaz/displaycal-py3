#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# Work-around 'Invalid handle' error on Windows when writing to stdout
sys.stdout = sys.stderr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import colormath as cm
from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL import worker
from DisplayCAL.wxwindows import BaseApp, wx

# Environment sets defaults
CAL_ONLY = int(os.getenv("CHANGE_DISPLAY_PROFILE_WTPT_CAL_ONLY", 0))
USE_COLLINK = int(os.getenv("CHANGE_DISPLAY_PROFILE_WTPT_USE_COLLINK", 0))


def main(*args, **kwargs):
    # Parse arguments
    cal_only = kwargs.get("--cal-only", CAL_ONLY)
    state = None
    xy = None
    profile = None
    outfilename = None
    for i, arg in enumerate(args):
        if arg == "-t":
            state = "COLORTEMP_DAYLIGHT"
        elif arg == "-T":
            state = "COLORTEMP_BLACKBODY"
        elif (
            arg.startswith("-t")
            or arg.startswith("-T")
            or state in ("COLORTEMP_DAYLIGHT", "COLORTEMP_BLACKBODY")
        ):
            if state in ("COLORTEMP_DAYLIGHT", "COLORTEMP_BLACKBODY"):
                ctstr = arg
            else:
                ctstr = arg[2:]
            try:
                ct = float(ctstr)
            except ValueError:
                raise Invalid("Invalid color temperature %s" % ctstr)
            if arg.startswith("-t") or state == "COLORTEMP_DAYLIGHT":
                xy = cm.CIEDCCT2xyY(ct)
                if not xy:
                    raise Invalid("Daylight color temperature %i out of range" % ct)
            else:
                xy = cm.planckianCT2xyY(ct)
                if not xy:
                    raise Invalid("Blackbody color temperature %i out of range" % ct)
            state = None
        elif arg == "-w":
            state = "CHROMATICITY"
        elif arg.startswith("-w") or state == "CHROMATICITY":
            if state == "CHROMATICITY":
                xystr = arg
            else:
                xystr = arg[2:]
            xy = xystr.split(",")
            if len(xy) != 2:
                raise Invalid("Invalid chromaticity: %s" % xystr)
            try:
                xy = [float(v) for v in xy]
            except ValueError:
                raise Invalid("Invalid chromaticity %s" % xystr)
            state = None
        elif os.path.isfile(arg) and i < len(args) - 1:
            print("Reading profile:", arg)
            profile = ICCP.ICCProfile(arg)
        else:
            outfilename = os.path.abspath(arg)
    if not xy or not outfilename:
        raise Invalid(
            "Usage: %s [-t temp | -T temp | -w x,y] [--cal-only] [inprofile] outfilename"
            % os.path.basename(__file__)
        )
    if not profile:
        print("Reading display profile")
        profile = ICCP.get_display_profile()
    # Setup
    config.initcfg()
    lang.init()
    w = worker.Worker()
    fn = w.change_display_profile_cal_whitepoint
    args = profile, xy[0], xy[1], outfilename, cal_only, USE_COLLINK
    # Process
    if CAL_ONLY:
        fn(*args)
    else:
        app = BaseApp(0)
        app.TopWindow = wx.Frame(None)
        w.start(
            lambda result: app.ExitMainLoop(),
            fn,
            wargs=args,
            progress_msg=lang.getstr("create_profile"),
        )
        app.MainLoop()


class Invalid(ValueError):
    pass


if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except Invalid as exception:
        print(exception)
