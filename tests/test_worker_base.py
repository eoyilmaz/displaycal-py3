# -*- coding: utf-8 -*-

from DisplayCAL import worker_base


def test_printcmdline_1():
    """Test worker_base.printcmdline() function for issue #73"""
    # Command line:
    cmd = "/home/eoyilmaz/.local/bin/Argyll_V2.3.0/bin/colprof"
    args = [
        "-v",
        "-qh",
        "-ax",
        "-bn",
        "-C",
        b"No copyright. Created with DisplayCAL 3.8.9.3 and Argyll CMS 2.3.0",
        "-A",
        "Dell, Inc.",
        "-D",
        "UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
        "/tmp/DisplayCAL-i91d9z8_/UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
    ]
    # fn = "<bound method WorkerBase.log of <DisplayCAL.worker.Worker object at 0x7f7b941bb6a0>>"
    cwd = "/tmp/DisplayCAL-i91d9z8_"
    worker_base.printcmdline(cmd=cmd, args=args, cwd=cwd)
