#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from time import strftime


if __name__ == "__main__":
    if len(sys.argv) in (3, 4):
        curve = []
        start = float(sys.argv[1]) / 100
        end = float(sys.argv[2]) / 100
        steps = 256
        if len(sys.argv) > 3:
            steps = int(sys.argv[3])
        if start == end:
            print("ERROR: start == end")
        else:
            step = (end - start) / (steps - 1)
            i = start
            for _x in range(steps):
                curve += [i]
                i += step
            if curve[-1] != end:
                curve += [end]
            print("CAL    ")
            print("")
            print('DESCRIPTOR "Argyll Device Calibration Curves"')
            print('ORIGINATOR "lincal.py"')
            print('CREATED "%s"' % strftime("%a %b %d %H:%I:%S %Y"))
            print('KEYWORD "DEVICE_CLASS"')
            print('DEVICE_CLASS "DISPLAY"')
            print('KEYWORD "COLOR_REP"')
            print('COLOR_REP "RGB"')
            print("")
            print('KEYWORD "RGB_I"')
            print("NUMBER_OF_FIELDS 4")
            print("BEGIN_DATA_FORMAT")
            print("RGB_I RGB_R RGB_G RGB_B")
            print("END_DATA_FORMAT")
            print("")
            print("NUMBER_OF_SETS %i" % steps)
            print("BEGIN_DATA")
            for i in range(steps):
                print(
                    " ".join(
                        [
                            str(round(col, 7 if col < 0.1 else 6)).ljust(7, "0")
                            for col in [(1.0 / (steps - 1)) * i] + [curve[i]] * 3
                        ]
                    )
                )
            print("END_DATA")
    else:
        print("Usage: %s start end steps" % os.path.basename(__file__))
        print(" start, end = integer between 0 and 100")
        print(" steps = number of steps (default 256)")
