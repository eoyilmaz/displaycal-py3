#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import CGATS, ICCProfile as ICCP, argyll_cgats, config, colormath as cm
from DisplayCAL.worker import Worker, Xicclu, get_argyll_util, _applycal_bug_workaround


cgats_header = """CAL
ORIGINATOR "Argyll dispcal"
CREATED "Thu Aug 01 00:00:00 2019"
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB"
VIDEO_LUT_CALIBRATION_POSSIBLE "YES"
TV_OUTPUT_ENCODING "NO"

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
RGB_I RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 256
BEGIN_DATA
"""


def get_cal(
    num_cal_entries,
    target_whitepoint,
    gamma,
    profile,
    intent="r",
    direction="if",
    order="n",
    slope_limit=0,
):
    maxval = num_cal_entries - 1.0

    # Get profile black and white point XYZ
    XYZbp, XYZwp = get_bkpt_wtpt(profile, intent, "f", order)

    if target_whitepoint:
        XYZwp = target_whitepoint

    # Calibrated XYZ
    idata = []
    for i in range(num_cal_entries):
        XYZ = cm.adapt(
            *[cm.specialpow(i / maxval, gamma, slope_limit)] * 3,
            whitepoint_source=(1, 1, 1),
            whitepoint_destination=XYZwp
        )
        XYZ = cm.blend_blackpoint(*XYZ, bp_in=(0, 0, 0), bp_out=XYZbp, wp=XYZwp)
        idata.append(XYZ)

    # Lookup calibration (target) XYZ through profile (inverse forward)
    xicclu_invfwd = Xicclu(profile, intent, direction, order, "x")
    xicclu_invfwd(idata)
    xicclu_invfwd.exit()

    # Get calibrated RGB
    odata = xicclu_invfwd.get(get_clip=direction == "if")

    if direction == "if":
        Lbp = 0

        # Deal with values that got clipped (below black as well as white)
        do_low_clip = True
        for i, values in enumerate(odata):
            if values[3] is True or i == 0:
                if do_low_clip and (i / maxval * 100 < Lbp or i == 0):
                    # Set to black
                    values[:] = [0.0, 0.0, 0.0]
                elif i == maxval and [round(v, 4) for v in values[:3]] == [1, 1, 1]:
                    # Set to white
                    values[:] = [1.0, 1.0, 1.0]
            else:
                # First non-clipping value disables low clipping
                do_low_clip = False
            if len(values) > 3:
                values.pop()

    return odata


def get_interp(cal, inverse=False, smooth=False):
    num_cal_entries = len(cal)
    cal_entry_max = num_cal_entries - 1.0

    linear = [(i / cal_entry_max,) * 3 for i in range(num_cal_entries)]

    if smooth:
        for lower, row in enumerate(cal[1:], 1):
            v = min(row) * cal_entry_max
            print(lower / cal_entry_max * 255, "->", v / cal_entry_max * 255)
            if lower + 1 >= v >= lower or lower / cal_entry_max * 255 >= 8:
                # Use max index of 4 (+ 2 = 6 = ~2% signal)
                if lower == 1:
                    # First value already above threshold, disable smoothing
                    lower = 0
                else:
                    print("lower", lower)
                break
        t = num_cal_entries // 128
        for i in range(3):
            values = cm.make_monotonically_increasing([v[i] for v in cal])
            if lower:
                # values[:lower] = cm.smooth_avg(values[:lower], 3, (1,) * 3)
                values[:lower] = [
                    j / float(lower) * values[lower] for j in range(lower)
                ]
                if lower < num_cal_entries:
                    # Smooth up to ~5% signal
                    start, end = max(lower - t * 2, 0), lower + t * 2
                    print("start, end", start, end)
                    values[start:end] = cm.smooth_avg(
                        values[start:end], 1, (1,) * (t + 1)
                    )
            values[:] = cm.smooth_avg(values[:], 1, (1,) * (t + 1))
            for j, v in enumerate(values):
                cal[j][i] = v

    if inverse:
        xp = cal
        fp = linear
    else:
        xp = linear
        fp = cal

    interp = []
    for i in range(3):
        interp.append(cm.Interp([v[i] for v in xp], [v[i] for v in fp], use_numpy=True))

    return interp


def get_bkpt_wtpt(profile, intent, direction="f", order="n"):
    xicclu_fwd = Xicclu(profile, intent, direction, order, "x")
    xicclu_fwd([(0, 0, 0), (1, 1, 1)])
    xicclu_fwd.exit()
    return xicclu_fwd.get()


def main(icc_profile_filename, target_whitepoint=None, gamma=2.2, skip_cal=False):
    profile = ICCP.ICCProfile(icc_profile_filename)

    worker = Worker()

    if target_whitepoint:
        intent = "a"
    else:
        intent = "r"

    gamma = float(gamma)

    num_cal_entries = 4096
    # cal_entry_max = num_cal_entries - 1.0

    ogamma = {
        -2.4: "sRGB",
        -3.0: "LStar",
        -2084: "SMPTE2084",
        -709: "BT709",
        -240: "SMPTE240M",
        -601: "BT601",
    }.get(gamma, gamma)
    owtpt = target_whitepoint and ".%s" % target_whitepoint or ""

    filename, ext = os.path.splitext(icc_profile_filename)

    # Get existing calibration CGATS from profile
    existing_cgats = argyll_cgats.extract_cal_from_profile(
        profile, raise_on_missing_cal=False
    )

    # Enabling this will do a linear blend below interpolation threshold, which
    # is probably not what we want - rather, the original cal should blend into
    # the linear portion
    applycal = False

    applycal_inverse = not list(
        filter(
            lambda tagname: tagname.startswith("A2B") or tagname.startswith("B2A"),
            profile.tags,
        )
    )
    print("Use applycal to apply cal?", applycal)
    print("Use applycal to apply inverse cal?", applycal_inverse)
    print("Ensuring 256 entry TRC tags")
    _applycal_bug_workaround(profile)
    existing_cgats_filename = f"{filename}.tmp.cal"
    input_color_profile_filename = f"{filename}.tmp{ext}"
    out_color_profile_filename = f"{filename}.calapplied{ext}"
    if (applycal or applycal_inverse) and existing_cgats:
        print("Writing TMP profile for applycal")
        profile.write(input_color_profile_filename)

    if applycal and existing_cgats:
        # Apply cal
        existing_cgats.write(existing_cgats_filename)
        result = worker.exec_cmd(
            get_argyll_util("applycal"),
            [
                "-v",
                existing_cgats_filename,
                input_color_profile_filename,
                out_color_profile_filename,
            ],
            capture_output=True,
            log_output=True,
        )
        if not result and not os.path.isfile(out_color_profile_filename):
            raise Exception("applycal returned a non-zero exit code")
        elif isinstance(result, Exception):
            raise result
        calapplied = ICCP.ICCProfile(out_color_profile_filename)
    else:
        calapplied = profile

    if target_whitepoint:
        try:
            target_whitepoint = float(target_whitepoint)
        except ValueError:
            pass
        target_whitepoint = cm.get_whitepoint(target_whitepoint)

        # target_whitepoint = cm.adapt(*target_whitepoint,
        # whitepoint_source=profile.tags.wtpt.ir.values())

        logfiles = sys.stdout

        # Lookup scaled down white XYZ
        logfiles.write("Looking for solution...\n")
        for n in range(9):
            XYZscaled = []
            for i in range(2001):
                XYZscaled.append(
                    [v * (1 - (n * 2001 + i) / 20000.0) for v in target_whitepoint]
                )
            RGBscaled = worker.xicclu(
                profile, XYZscaled, intent, "if", pcs="x", get_clip=True
            )
            # Find point at which it no longer clips
            XYZwscaled = None
            for i, RGBclip in enumerate(RGBscaled):
                if RGBclip[3] is True or max(RGBclip[:3]) > 1:
                    # Clipped, skip
                    continue
                # Found
                XYZwscaled = XYZscaled[i]
                logfiles.write(
                    "Solution found at index %i " "(step size %f)\n" % (i, 1 / 2000.0)
                )
                logfiles.write("RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBclip[:3]))
                logfiles.write(
                    "XYZ white %6.4f %6.4f %6.4f, "
                    "CCT %.1f K\n" % tuple(XYZscaled[i] + [cm.XYZ2CCT(*XYZwscaled)])
                )
                break
            else:
                if n == 8:
                    break
            if XYZwscaled:
                # Found solution
                break
        if not XYZwscaled:
            raise Exception(
                "No solution found in %i " "iterations with %i steps" % (n, i)
            )
        target_whitepoint = XYZwscaled
        del RGBscaled

    if not applycal or applycal_inverse:
        ccal = get_cal(
            num_cal_entries,
            target_whitepoint,
            gamma,
            profile,
            intent,
            "if",
            slope_limit=0,
        )

    out_color_profile_filename = (
        filename
        + " %s%s" % (target_whitepoint and "%s " % owtpt[1:] or "", ogamma)
        + ext
    )

    if target_whitepoint is False:  # NEVER
        # Apply inverse CAL with PCS white
        main(icc_profile_filename, gamma=gamma, skip_cal=True)
    else:
        # Generate inverse calibration

        # Apply inverse CAL and write output file
        if not applycal_inverse:
            # Use our own code

            TRC = []

            seen = []

            for tagname in (
                "A2B0",
                "A2B1",
                "A2B2",
                "B2A0",
                "B2A1",
                "B2A2",
                "rTRC",
                "gTRC",
                "bTRC",
            ):
                if tagname not in profile.tags:
                    continue
                print(tagname)
                if profile.tags[tagname] in seen:
                    print("Already seen")
                    continue
                seen.append(profile.tags[tagname])
                if tagname.startswith("A2B"):
                    # Apply calibration to input curves
                    cal = get_cal(num_cal_entries, None, gamma, profile, intent, "if")
                    interp_i = get_interp(cal, True)
                    entries = profile.tags[tagname].input
                elif tagname.startswith("B2A"):
                    # Apply inverse calibration to output curves
                    if profile.tags[tagname].clut_grid_steps <= 9:
                        # Low quality. Skip.
                        print("Low quality, skipping")
                        continue
                    cal = get_cal(num_cal_entries, None, gamma, profile, intent, "b")
                    interp_i = get_interp(cal, True)
                    entries = profile.tags[tagname].output
                else:
                    entries = profile.tags[tagname]
                    TRC.append(entries[:])
                    num_entries = len(entries)
                    j = "rgb".index(tagname[0])
                    cal = get_cal(
                        num_cal_entries, None, gamma, profile, intent, "if", "r"
                    )
                    interp_i = get_interp(cal, True)
                    cinterp = cm.Interp(
                        [
                            interp_i[j](i / (num_entries - 1.0))
                            for i in range(num_entries)
                        ],
                        entries,
                        use_numpy=True,
                    )
                    entries[:] = [
                        cinterp(i / (num_entries - 1.0)) for i in range(num_entries)
                    ]
                    continue
                for j in range(3):
                    num_entries = len(entries[j])
                    if tagname.startswith("A2B"):
                        cinterp = cm.Interp(
                            [
                                interp_i[j](i / (num_entries - 1.0))
                                for i in range(num_entries)
                            ],
                            [v / 65535.0 for v in entries[j]],
                            use_numpy=True,
                        )
                    elif tagname.startswith("B2A"):
                        rinterp = cm.Interp(
                            [v / 65535.0 for v in entries[j]],
                            [i / (num_entries - 1.0) for i in range(num_entries)],
                            use_numpy=True,
                        )
                        cinterp = cm.Interp(
                            [
                                rinterp(i / (num_entries - 1.0))
                                for i in range(num_entries)
                            ],
                            [
                                interp_i[j](i / (num_entries - 1.0))
                                for i in range(num_entries)
                            ],
                            use_numpy=True,
                        )
                    entries[j] = []
                    num_entries = max(num_entries, 256)
                    for i in range(num_entries):
                        entries[j].append(
                            min(max(cinterp(i / (num_entries - 1.0)) * 65535, 0), 65535)
                        )

            # Check for identical initial TRC tags, and force them identical again
            if TRC and TRC.count(TRC[0]) == 3:
                print("Forcing identical TRC tags")
                for channel in "rb":
                    profile.tags[channel + "TRC"] = profile.tags.gTRC

        elif existing_cgats:
            # Use Argyll applycal
            # XXX: Want to derive different cals for cLUT and TRC tags.
            # Not possible with applycal unless applying cals separately and
            # combining the profile parts later?

            # Get inverse calibration
            interp_i = get_interp(ccal, True)
            ical = []
            # Argyll can only deal with 256 cal entries
            for i in range(256):
                ical.append([cinterp(i / 255.0) for cinterp in interp_i])

            # Write inverse CAL
            icgats = cgats_header
            for i, (R, G, B) in enumerate(ical):
                icgats += "%.7f %.7f %.7f %.7f\n" % (i / 255.0, R, G, B)
            icgats += "END_DATA\n"
            ical_filename = icc_profile_filename + owtpt + ".%s.inverse.cal" % ogamma
            with open(ical_filename, "wb") as f:
                f.write(icgats.encode())

            result = worker.exec_cmd(
                get_argyll_util("applycal"),
                ["-v", ical_filename, filename + ".tmp" + ext, out_color_profile_filename],
                capture_output=True,
                log_output=True,
            )
            if not result and not os.path.isfile(out_color_profile_filename):
                raise Exception("applycal returned a non-zero exit code")
            elif isinstance(result, Exception):
                raise result

            profile = ICCP.ICCProfile(out_color_profile_filename)

    out_profile = profile

    if not skip_cal:
        # Improve existing calibration with new calibration

        if applycal:
            ccal = get_cal(
                256, target_whitepoint, gamma, calapplied, intent, "if", slope_limit=0
            )
            num_cal_entries = len(ccal)
        else:
            if not existing_cgats:
                existing_cgats = CGATS.CGATS(config.get_data_path("linear.cal"))

            num_cal_entries = len(existing_cgats[0].DATA)

        cal_entry_max = num_cal_entries - 1.0

        if not applycal:
            interp = get_interp(ccal, False, True)

            # Create CAL diff
            cgats = cgats_header
            for i in range(num_cal_entries):
                RGB = [cinterp(i / cal_entry_max) for cinterp in interp]
                R, G, B = (min(max(v, 0), 1) for v in RGB)
                cgats += "%.7f %.7f %.7f %.7f\n" % (i / cal_entry_max, R, G, B)
            cgats += "END_DATA\n"
            with open(
                icc_profile_filename + owtpt + ".%s.diff.cal" % ogamma, "wb"
            ) as f:
                f.write(cgats.encode())

            cgats_cal_interp = []
            for _i in range(3):
                cgats_cal_interp.append(
                    cm.Interp([v / cal_entry_max for v in range(num_cal_entries)], [])
                )
            for _i, row in existing_cgats[0].DATA.items():
                for j, channel in enumerate("RGB"):
                    cgats_cal_interp[j].fp.append(row["RGB_" + channel])

        # Create CAL
        cgats = cgats_header
        for i in range(num_cal_entries):
            if applycal:
                RGB = [ccal[i][j] for j in range(3)]
            else:
                RGB = [
                    cgats_cal_interp[j](cinterp(i / cal_entry_max))
                    for j, cinterp in enumerate(interp)
                ]
            R, G, B = (min(max(v, 0), 1) for v in RGB)
            cgats += "%.7f %.7f %.7f %.7f\n" % (i / cal_entry_max, R, G, B)
        cgats += "END_DATA\n"
        with open(icc_profile_filename + owtpt + ".%s.cal" % ogamma, "wb") as f:
            f.write(cgats.encode())

        # Add CAL as vcgt to profile
        out_profile.tags.vcgt = argyll_cgats.cal_to_vcgt(cgats)

        if target_whitepoint:
            # Update wtpt tag
            (
                out_profile.tags.wtpt.X,
                out_profile.tags.wtpt.Y,
                out_profile.tags.wtpt.Z,
            ) = target_whitepoint

    # Write updated profile
    out_profile.setDescription(
        out_profile.getDescription()
        + " %s%s" % (target_whitepoint and "%s " % owtpt[1:] or "", ogamma)
    )
    out_profile.calculateID()
    out_profile.write(out_color_profile_filename)


if __name__ == "__main__":
    config.initcfg()
    main(*sys.argv[1:4])
