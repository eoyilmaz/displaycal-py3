#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(root)

from DisplayCAL import config, ICCProfile as ICCP, localization as lang, meta
from DisplayCAL.worker import Worker, check_argyll_bin, get_argyll_util


def create_testcharts(overwrite=False):
    min_bcc_steps, max_bcc_steps = 7, 11
    # Profile, amount of dark region emphasis
    precond = {
        "eRGBv2": (ICCP.ICCProfile("eciRGB_v2.icc").fileName, 1.0),
        "aRGB": (config.get_data_path("ref/ClayRGB1998.icm"), 1.6),
        "Rec709_Gamma22": (config.get_data_path("ref/Rec709_Gamma22.icm"), 1.6),
        "sRGB": (config.get_data_path("ref/sRGB.icm"), 1.6),
    }
    worker = Worker()
    targen = get_argyll_util("targen")
    for bcc_steps in range(min_bcc_steps, max_bcc_steps + 1):
        single_channel = bcc_steps * 4 - 3
        gray_channel = single_channel * 3 - 2
        total = config.get_total_patches(
            4, 4, single_channel, gray_channel, bcc_steps, bcc_steps, 0
        )
        for name in precond:
            filename, demphasis = precond[name]
            cwd = os.path.join(root, meta.name, "ti1")
            outname = "d3-e4-s%i-g%i-m0-f%i-c%s" % (
                single_channel,
                gray_channel,
                total,
                name,
            )
            if not os.path.isfile(os.path.join(cwd, outname + ".ti1")) or overwrite:
                result = worker.exec_cmd(
                    targen,
                    [
                        "-v",
                        "-d3",
                        "-e4",
                        "-s%i" % single_channel,
                        "-g%i" % gray_channel,
                        "-m0",
                        "-f%i" % total,
                        "-G",
                        "-c" + filename,
                        "-V%.1f" % demphasis,
                        outname,
                    ],
                    working_dir=cwd,
                    sessionlogfile=sys.stdout,
                )
                if isinstance(result, Exception):
                    print(result)
        worker.wrapup(False)


if __name__ == "__main__":
    config.initcfg()
    lang.init()
    if check_argyll_bin():
        create_testcharts("--overwrite" in sys.argv[1:])
    else:
        print("ArgyllCMS not found")
