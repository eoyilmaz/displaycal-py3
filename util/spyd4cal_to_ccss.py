#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from time import strftime
import math
import os
import sys


def buf2ord64(buf):
    val = ord(buf[7])
    val = (val << 8) + (0xFF & ord(buf[6]))
    val = (val << 8) + (0xFF & ord(buf[5]))
    val = (val << 8) + (0xFF & ord(buf[4]))
    val = (val << 8) + (0xFF & ord(buf[3]))
    val = (val << 8) + (0xFF & ord(buf[2]))
    val = (val << 8) + (0xFF & ord(buf[1]))
    val = (val << 8) + (0xFF & ord(buf[0]))
    return val


def IEEE754_64todouble(ip):
    sn = (ip >> 63) & 0x1
    ep = (ip >> 52) & 0x7FF
    ma = ip & ((1 << 52) - 1)
    if ep == 0:  # Zero or denormalized
        op = float(ma) / float(1 << 52)
        op *= math.pow(2.0, -1022.0)
    else:
        op = float(ma | (1 << 52)) / float(1 << 52)
        op *= math.pow(2.0, (int(ep) - 1023.0))
    if sn:
        op = -op
    return op


def readcals(filename):
    cals = []
    with open(filename, "rb") as f:
        buf = f.read()
        size = f.tell()
    for i in range(int(size / (41 * 8))):
        display = {
            0: "Identity",
            1: "LCD (CCFL)",
            2: "Wide Gamut LCD (CCFL)",
            3: "LCD (White LED)",
            4: "Wide Gamut LCD (RGB LED)",
            5: "LCD (CCFL Type 2)",
        }.get(i, "Unknown")
        tech = {
            0: "Identity",
            1: "LCD CCFL TFT",
            2: "LCD CCFL Wide Gamut TFT",
            3: "LCD White LED TFT",
            4: "LCD RGB LED TFT",
            5: "LCD CCFL TFT",
        }.get(i, "UNKNOWN")
        cal = Spyd4Cal(buf[41 * 8 * i: 41 * 8 * (i + 1)], display, tech)
        if sum(cal.spec) != len(cal.spec):
            cals.append(cal)
        else:
            print("Skipping identity cal", i)
    return cals


class Spyd4Cal:
    def __init__(self, buf, display, tech):
        self.display = display
        self.tech = tech
        self.start_nm = 380
        self.end_nm = 780
        self.norm = 1.0
        self.spec = []
        for i in range(int(len(buf) / 8)):
            val = buf2ord64(buf[8 * i: 8 * (i + 1)])
            self.spec.append(IEEE754_64todouble(val))

    def write_ccss(self, filename):
        with open(filename, "w") as f:
            f.write(
                """CCSS

ORIGINATOR "DataColor"
CREATED "%(date)s"
KEYWORD "DISPLAY"
DISPLAY "%(display)s (Spyder 4)"
KEYWORD "TECHNOLOGY"
TECHNOLOGY "%(tech)s"
KEYWORD "DISPLAY_TYPE_REFRESH"
DISPLAY_TYPE_REFRESH "NO"
KEYWORD "REFERENCE"
REFERENCE "Not specified"
KEYWORD "SPECTRAL_BANDS"
SPECTRAL_BANDS "%(bands)i"
KEYWORD "SPECTRAL_START_NM"
SPECTRAL_START_NM "%(start_nm).6f"
KEYWORD "SPECTRAL_END_NM"
SPECTRAL_END_NM "%(end_nm).6f"
KEYWORD "SPECTRAL_NORM"
SPECTRAL_NORM "%(norm).6f"
DESCRIPTOR "Not specified"

"""
                % {
                    "date": strftime("%a %b %d %H:%M:%S %Y"),
                    "display": self.display,
                    "tech": self.tech,
                    "bands": len(self.spec),
                    "start_nm": self.start_nm,
                    "end_nm": self.end_nm,
                    "norm": self.norm,
                }
            )
            for i, _spec in enumerate(self.spec):
                f.write(
                    'KEYWORD "SPEC_%i"\n'
                    % (
                        self.start_nm
                        + (self.end_nm - self.start_nm) / (len(self.spec) - 1) * i
                    )
                )
            f.write("NUMBER_OF_FIELDS %i\n" % (1 + len(self.spec)))
            f.write("BEGIN_DATA_FORMAT\n")
            f.write("SAMPLE_ID ")
            for i, _spec in enumerate(self.spec):
                f.write(
                    "SPEC_%i "
                    % (
                        self.start_nm
                        + (self.end_nm - self.start_nm) / (len(self.spec) - 1) * i
                    )
                )
            f.write(
                """
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
"""
            )
            for n in range(3):
                f.write("%i " % (n + 1))
                for spec in self.spec:
                    f.write("%.6f " % spec)
                f.write("\n")
            f.write("END_DATA\n")


if __name__ == "__main__":
    for spyd4cal in sys.argv[1:]:
        for cal in readcals(spyd4cal):
            cal.write_ccss(
                os.path.join(
                    os.path.dirname(spyd4cal), "%s (Spyder 4).ccss" % cal.display
                )
            )
