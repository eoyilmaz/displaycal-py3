# -*- coding: utf-8 -*-

# import decimal
# Decimal = decimal.Decimal
import decimal
from decimal import Decimal
import os
import traceback
from io import BytesIO
from time import strftime

from DisplayCAL.debughelpers import Error
from DisplayCAL.options import debug
from DisplayCAL import CGATS
from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import colormath
from DisplayCAL import localization as lang

cals = {}


def quote_nonoption_args(args):
    """Put quotes around all arguments which are not options.

    (ie. which do not start with a hyphen '-')
    """
    args = list(args)
    for i, arg in enumerate(args):
        # first convert everything to bytes
        if not isinstance(arg, bytes):
            arg = bytes(str(arg), "utf-8")
        args[i] = b'"%s"' % arg if arg[:1] != b"-" else arg
    return args


def add_dispcal_options_to_cal(cal, options_dispcal):
    # Add dispcal options to cal
    options_dispcal = quote_nonoption_args(options_dispcal)
    try:
        cgats = CGATS.CGATS(cal)
        cgats[0].add_section("ARGYLL_DISPCAL_ARGS", b" ".join(options_dispcal))
        return cgats
    except Exception:
        print(traceback.format_exc())


def add_options_to_ti3(ti3, options_dispcal=None, options_colprof=None):
    # Add dispcal and colprof options to ti3
    try:
        cgats = CGATS.CGATS(ti3)
        if options_colprof:
            options_colprof = quote_nonoption_args(options_colprof)
            cgats[0].add_section(
                "ARGYLL_COLPROF_ARGS",
                b" ".join(options_colprof),
            )

        if options_dispcal and 1 in cgats:
            options_dispcal = quote_nonoption_args(options_dispcal)
            cgats[1].add_section(
                "ARGYLL_DISPCAL_ARGS",
                b" ".join(options_dispcal),
            )
        return cgats
    except BaseException:
        print(traceback.format_exc())


def cal_to_fake_profile(cal):
    """Create and return a 'fake' ICCProfile with just a vcgt tag.

    cal must refer to a valid Argyll CAL file and can be a CGATS instance
    or a filename.
    """
    vcgt, cal = cal_to_vcgt(cal, True)
    if not vcgt:
        return
    profile = ICCP.ICCProfile()
    profile.fileName = cal.filename
    profile._data = b"\0" * 128
    profile._tags.desc = ICCP.TextDescriptionType(b"", "desc")
    profile._tags.desc.ASCII = str(os.path.basename(cal.filename)).encode(
        "ascii", "asciize"
    )
    profile._tags.desc.Unicode = str(os.path.basename(cal.filename))
    profile._tags.vcgt = vcgt
    profile.size = len(profile.data)
    profile.is_loaded = True
    return profile


def cal_to_vcgt(cal, return_cgats=False):
    """Create a vcgt tag from calibration data.

    cal must refer to a valid Argyll CAL file and can be a CGATS instance
    or a filename.
    """
    if not isinstance(cal, CGATS.CGATS):
        try:
            cal = CGATS.CGATS(cal)
        except (
            IOError,
            CGATS.CGATSInvalidError,
            CGATS.CGATSInvalidOperationError,
            CGATS.CGATSKeyError,
            CGATS.CGATSTypeError,
            CGATS.CGATSValueError,
        ) as exception:
            print(f"Warning - couldn't process CGATS file '{cal}': {exception}")
            return None
    required_fields = ("RGB_I", "RGB_R", "RGB_G", "RGB_B")
    if data_format := cal.queryv1("DATA_FORMAT"):
        for field in required_fields:
            if field.encode("utf-8") not in list(data_format.values()):
                if debug:
                    print(f"[D] Missing required field: {field}")
                return None
        for field in list(data_format.values()):
            if field.decode("utf-8") not in required_fields:
                if debug:
                    print(f"[D] Unknown field: {field}")
                return None
    entries = cal.queryv(required_fields)
    if len(entries) < 1:
        if debug:
            print(f"[D] No entries found in calibration {cal.filename}")
        return None
    vcgt = ICCP.VideoCardGammaTableType(b"", "vcgt")
    vcgt.update(
        {
            "channels": 3,
            "entryCount": len(entries),
            "entrySize": 2,
            "data": [[], [], []],
        }
    )
    for n in entries:
        for i in range(3):
            vcgt.data[i].append(entries[n][i + 1] * 65535.0)
    if return_cgats:
        return vcgt, cal
    return vcgt


def can_update_cal(path):
    """Check if cal can be updated by checking for required fields."""
    try:
        calstat = os.stat(path)
    except Exception as exception:
        print(f"Warning - os.stat('{path}') failed: {exception}")
        return False
    if path not in cals or cals[path].mtime != calstat.st_mtime:
        try:
            cal = CGATS.CGATS(path)
        except (
            IOError,
            CGATS.CGATSInvalidError,
            CGATS.CGATSInvalidOperationError,
            CGATS.CGATSKeyError,
            CGATS.CGATSTypeError,
            CGATS.CGATSValueError,
        ) as exception:
            if path in cals:
                del cals[path]
            print(f"Warning - couldn't process CGATS file '{path}': {exception}")
        else:
            if cal.queryv1("DEVICE_CLASS") == "DISPLAY" and None not in (
                cal.queryv1("TARGET_WHITE_XYZ"),
                cal.queryv1("TARGET_GAMMA"),
                cal.queryv1("BLACK_POINT_CORRECTION"),
                cal.queryv1("QUALITY"),
            ):
                cals[path] = cal
    return path in cals and cals[path].mtime == calstat.st_mtime


def extract_cal_from_profile(
    profile, out_cal_path=None, raise_on_missing_cal=True, prefer_cal=False
):
    """Extract calibration from 'targ' tag in profile or vcgt as fallback"""
    white = False

    # Check if calibration is included in TI3
    targ = profile.tags.get("targ", profile.tags.get("CIED"))
    if isinstance(targ, ICCP.Text):
        cal = extract_cal_from_ti3(targ)
        if cal:
            check = cal
            get_cgats = CGATS.CGATS
            arg = cal
    else:
        cal = None
    if not cal:
        # Convert calibration information from embedded WCS profile
        # (if present) to VideCardFormulaType if the latter is not present
        if (
            isinstance(profile.tags.get("MS00"), ICCP.WcsProfilesTagType)
            and "vcgt" not in profile.tags
        ):
            profile.tags["vcgt"] = profile.tags["MS00"].get_vcgt()

        # Get the calibration from profile vcgt
        check = isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
        get_cgats = vcgt_to_cal
        arg = profile

    if check:
        try:
            cgats = get_cgats(arg)
        except (IOError, CGATS.CGATSError) as e:
            traceback.print_exc()
            raise Error(lang.getstr("cal_extraction_failed")) from e
    elif raise_on_missing_cal:
        raise Error(lang.getstr("profile.no_vcgt"))
    else:
        return False
    if (
        cal
        and not prefer_cal
        and isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
    ):
        # When vcgt is nonlinear, prefer it
        # Check for video levels encoding
        if cgats.queryv1("TV_OUTPUT_ENCODING") == b"YES":
            black, white = (16, 235)
        elif output_enc := cgats.queryv1("OUTPUT_ENCODING"):
            try:
                black, white = (float(v) for v in output_enc.split())
            except (TypeError, ValueError):
                white = False
        cgats = vcgt_to_cal(profile)
        if white and (black, white) != (0, 255):
            print(f"Need to un-scale vcgt from video levels ({black}..{white})")
            # Need to un-scale video levels
            if data := cgats.queryv1("DATA"):
                print(f"Un-scaling vcgt from video levels ({black}..{white})")
                encoding_mismatch = False
                # For video encoding the extra bits of
                # precision are created by bit shifting rather
                # than scaling, so we need to scale the fp
                # value to account for this
                oldmin = (black / 256.0) * (65536 / 65535.0)
                oldmax = (white / 256.0) * (65536 / 65535.0)
                for entry in data.values():
                    for column in "RGB":
                        v_old = entry[f"RGB_{column}"]
                        lvl = round(v_old * (65535 / 65536.0) * 256, 2)
                        if lvl < round(black, 2) or lvl > round(white, 2):
                            # Can't be right. Metadata says it's video encoded,
                            # but clearly exceeds the encoding range.
                            print(
                                f"Warning: Metadata claims video levels ("
                                f"{round(black, 2)}..{round(white, 2)}) but "
                                f"vcgt value {lvl} exceeds encoding range. "
                                f"Using values as-is."
                            )
                            encoding_mismatch = True
                            break
                        v_new = colormath.convert_range(v_old, oldmin, oldmax, 0, 1)
                        entry[f"RGB_{column}"] = min(max(v_new, 0), 1)
                    if encoding_mismatch:
                        break
                if encoding_mismatch:
                    cgats = vcgt_to_cal(profile)
                # Add video levels hint to CGATS
                elif (black, white) == (16, 235):
                    cgats[0].add_keyword("TV_OUTPUT_ENCODING", "YES")
                else:
                    cgats[0].add_keyword(
                        "OUTPUT_ENCODING",
                        b" ".join(bytes(str(v), "utf-8") for v in (black, white)),
                    )
            else:
                print("Warning - no un-scaling applied - no calibration data!")
    if out_cal_path:
        cgats.write(out_cal_path)
    return cgats


def extract_cal_from_ti3(ti3):
    """Extract and return the CAL section of a TI3.

    ti3 can be a file object or a string holding the data.
    """
    if isinstance(ti3, CGATS.CGATS):
        ti3 = bytes(ti3)
    if isinstance(ti3, bytes):
        ti3 = BytesIO(ti3)
    cal = False
    cal_lines = []
    for line in ti3:
        line = line.strip()
        if line == b"CAL":
            line = b"CAL    "  # Make sure CGATS file identifiers are
            # always a minimum of 7 characters
            cal = True
        if cal:
            cal_lines.append(line)
            if line == b"END_DATA":
                break
    try:
        ti3.close()
    except AttributeError:
        pass

    return b"\n".join(cal_lines)


def extract_fix_copy_cal(source_filename, target_filename=None):
    """Return the CAL section from a profile's embedded measurement data.

    Try to 'fix it' (add information needed to make the resulting .cal file
    'updateable') and optionally copy it to target_filename.
    """
    from DisplayCAL.worker import get_options_from_profile

    try:
        profile = ICCP.ICCProfile(source_filename)
    except (IOError, ICCP.ICCProfileInvalidError) as exception:
        return exception
    if "CIED" not in profile.tags and "targ" not in profile.tags:
        return None
    cal_lines = []
    ti3 = BytesIO(profile.tags.get("CIED", b"") or profile.tags.get("targ", b""))
    ti3_lines = [line.strip() for line in ti3]
    ti3.close()
    cal_found = False
    for line in ti3_lines:
        line = line.strip()
        if line == b"CAL":
            line = b"CAL    "  # Make sure CGATS file identifiers are always a minimum of 7 characters
            cal_found = True
        if cal_found:
            cal_lines.append(line)
            if line == b'DEVICE_CLASS "DISPLAY"':
                if options_dispcal := get_options_from_profile(profile)[0]:
                    whitepoint = False
                    # b = profile.tags.lumi.Y
                    for o in options_dispcal:
                        if o[0] == b"y":
                            cal_lines.append(b'KEYWORD "DEVICE_TYPE"')
                            if o[1] == b"c":
                                cal_lines.append(b'DEVICE_TYPE "CRT"')
                            else:
                                cal_lines.append(b'DEVICE_TYPE "LCD"')
                            continue
                        if o[0] in (b"t", b"T"):
                            continue
                        if o[0] == b"w":
                            continue
                        if o[0] in (b"g", b"G"):
                            if o[1:] == b"240":
                                trc = b"SMPTE240M"
                            elif o[1:] == b"709":
                                trc = b"REC709"
                            elif o[1:] == b"l":
                                trc = b"L_STAR"
                            elif o[1:] == b"s":
                                trc = b"sRGB"
                            else:
                                trc = o[1:]
                                if o[0] == b"G":
                                    try:
                                        trc = 0 - Decimal(trc)
                                    except decimal.InvalidOperation:
                                        continue
                            cal_lines.extend(
                                (b'KEYWORD "TARGET_GAMMA"', b'TARGET_GAMMA "%s"' % trc)
                            )
                            continue
                        if o[0] == b"f":
                            cal_lines.extend(
                                (
                                    b'KEYWORD "DEGREE_OF_BLACK_OUTPUT_OFFSET"',
                                    b'DEGREE_OF_BLACK_OUTPUT_OFFSET "%s"' % o[1:],
                                )
                            )

                            continue
                        if o[0] == b"k":
                            cal_lines.extend(
                                (
                                    b'KEYWORD "BLACK_POINT_CORRECTION"',
                                    b'BLACK_POINT_CORRECTION "%s"' % o[1:],
                                )
                            )

                            continue
                        if o[0] == b"B":
                            cal_lines.extend(
                                (
                                    b'KEYWORD "TARGET_BLACK_BRIGHTNESS"',
                                    b'TARGET_BLACK_BRIGHTNESS "%s"' % o[1:],
                                )
                            )

                            continue
                        if o[0] == b"q":
                            if o[1] == b"l":
                                q = b"low"
                            elif o[1] == b"m":
                                q = b"medium"
                            else:
                                q = b"high"
                            cal_lines.extend(
                                (b'KEYWORD "QUALITY"', b'QUALITY "%s"' % q)
                            )
                    if not whitepoint:
                        cal_lines.extend(
                            (
                                b'KEYWORD "NATIVE_TARGET_WHITE"',
                                b'NATIVE_TARGET_WHITE ""',
                            )
                        )
    if cal_lines:
        if target_filename:
            try:
                with open(target_filename, "wb") as f:
                    f.write(b"\n".join(cal_lines))
            except Exception as exception:
                return exception
        return cal_lines


def extract_device_gray_primaries(
    ti3, gray=True, logfn=None, include_neutrals=False, neutrals_ab_threshold=0.1
):
    """Extract gray or primaries into new TI3

    Return extracted ti3, extracted RGB to XYZ mapping and remaining RGB to XYZ
    """
    filename = ti3.filename
    ti3 = ti3.queryi1("DATA")
    ti3.filename = filename
    ti3_extracted = CGATS.CGATS(
        b"""CTI3
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB_XYZ"
BEGIN_DATA_FORMAT
END_DATA_FORMAT
BEGIN_DATA
END_DATA"""
    )[0]
    ti3_extracted.DATA_FORMAT.update(ti3.DATA_FORMAT)
    subset = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
    if not gray:
        subset.extend(
            [
                (100.0, 0.0, 0.0),
                (0.0, 100.0, 0.0),
                (0.0, 0.0, 100.0),
                (50.0, 50.0, 50.0),
            ]
        )
        if logfn:
            logfn(f"Extracting neutrals and primaries from {ti3.filename}")
    elif logfn:
        logfn(f"Extracting neutrals from {ti3.filename}")
    RGB_XYZ_extracted = {}
    RGB_XYZ_remaining = {}
    dupes = {}
    if include_neutrals:
        white = ti3.get_white_cie("XYZ")
        str_thresh = str(neutrals_ab_threshold)
        round_digits = len(str_thresh[str_thresh.find(".") + 1 :])
    for i in ti3.DATA:
        item = ti3.DATA[i]
        if not i:
            # Check if fields are missing
            for prefix in ("RGB", "XYZ"):
                for suffix in prefix:
                    key = f"{prefix}_{suffix}"
                    if key not in item:
                        raise Error(
                            lang.getstr(
                                "error.testchart.missing_fields", (ti3.filename, key)
                            )
                        )
        RGB = (item["RGB_R"], item["RGB_G"], item["RGB_B"])
        XYZ = (item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"])
        for RGB_XYZ in (RGB_XYZ_extracted, RGB_XYZ_remaining):
            if RGB in RGB_XYZ:
                if RGB != (100.0, 100.0, 100.0):
                    # Add to existing values for averaging later
                    # if it's not white (all other readings are scaled to the
                    # white Y by dispread, so we don't alter it. Note that it's
                    # always the first encountered white that will have Y = 100,
                    # even if subsequent white readings may be higher)
                    XYZ = tuple(RGB_XYZ[RGB][i] + XYZ[i] for i in range(3))
                    if RGB not in dupes:
                        dupes[RGB] = 1.0
                    dupes[RGB] += 1.0
                elif RGB in subset:
                    # We have white already, remove it from the subset so any
                    # additional white readings we encounter are ignored
                    subset.remove(RGB)
        if (
            gray
            and (
                item["RGB_R"] == item["RGB_G"] == item["RGB_B"]
                or (
                    include_neutrals
                    and all(
                        round(abs(v), round_digits) <= neutrals_ab_threshold
                        for v in colormath.XYZ2Lab(
                            item["XYZ_X"],
                            item["XYZ_Y"],
                            item["XYZ_Z"],
                            whitepoint=white,
                        )[1:]
                    )
                )
            )
            and RGB not in [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
        ) or RGB in subset:
            ti3_extracted.DATA.add_data(item)
            RGB_XYZ_extracted[RGB] = XYZ
        elif RGB not in [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]:
            RGB_XYZ_remaining[RGB] = XYZ
    for RGB, count in dupes.items():
        for RGB_XYZ in (RGB_XYZ_extracted, RGB_XYZ_remaining):
            if RGB in RGB_XYZ:
                # Average values
                XYZ = tuple(RGB_XYZ[RGB][i] / count for i in range(3))
                RGB_XYZ[RGB] = XYZ
    return ti3_extracted, RGB_XYZ_extracted, RGB_XYZ_remaining


def ti3_to_ti1(ti3_data):
    """Create and return TI1 data converted from TI3.

    ti3_data can be a file object, a list of strings or a string holding the data.
    """
    ti3 = CGATS.CGATS(ti3_data)
    if not ti3:
        return ""
    ti3[0].type = b"CTI1"
    ti3[0].DESCRIPTOR = b"Argyll Calibration Target chart information 1"
    ti3[0].ORIGINATOR = b"Argyll targen"
    if hasattr(ti3[0], "COLOR_REP"):
        color_rep = ti3[0].COLOR_REP.split(b"_")[0]
    else:
        color_rep = b"RGB"
    ti3[0].add_keyword("COLOR_REP", color_rep)
    ti3[0].remove_keyword("DEVICE_CLASS")
    if hasattr(ti3[0], "LUMINANCE_XYZ_CDM2"):
        ti3[0].remove_keyword("LUMINANCE_XYZ_CDM2")
    if hasattr(ti3[0], "ARGYLL_COLPROF_ARGS"):
        del ti3[0].ARGYLL_COLPROF_ARGS
    return bytes(ti3[0])


def vcgt_to_cal(profile):
    """Return a CAL (CGATS instance) from vcgt."""
    cgats = CGATS.CGATS(file_identifier=b"CAL")
    context = cgats.add_data({"DESCRIPTOR": b"Argyll Device Calibration State"})
    context.add_data({"ORIGINATOR": b"vcgt"})
    context.add_data(
        {
            "CREATED": bytes(
                strftime("%a %b %d %H:%M:%S %Y", profile.dateTime.timetuple()),
                "utf-8",
                "replace",
            )
        }
    )
    context.add_keyword("DEVICE_CLASS", b"DISPLAY")
    context.add_keyword("COLOR_REP", b"RGB")
    context.add_keyword("RGB_I")
    key = "DATA_FORMAT"
    context[key] = CGATS.CGATS()
    context[key].key = key
    context[key].parent = context
    context[key].root = cgats
    context[key].type = key.encode("utf-8")
    context[key].add_data((b"RGB_I", b"RGB_R", b"RGB_G", b"RGB_B"))
    key = "DATA"
    context[key] = CGATS.CGATS()
    context[key].key = key
    context[key].parent = context
    context[key].root = cgats
    context[key].type = key.encode("utf-8")
    values = profile.tags.vcgt.getNormalizedValues()
    for i, triplet in enumerate(values):
        context[key].add_data((b"%.7f" % (i / float(len(values) - 1)),) + triplet)
    return cgats


def verify_cgats(cgats, required, ignore_unknown=True):
    """Verify and return a CGATS instance or None on failure.

    Verify if a CGATS instance has a section with all required fields.
    Return the section as CGATS instance on success, None on failure.

    If ignore_unknown evaluates to True, ignore fields which are not required.
    Otherwise, the CGATS data must contain only the required fields, no more,
    no less.
    """
    cgats_1 = cgats.queryi1(required)
    if not cgats_1 or not cgats_1.parent or not cgats_1.parent.parent:
        raise CGATS.CGATSKeyError(f'Missing required fields: {", ".join(required)}')
    cgats_1 = cgats_1.parent.parent
    if not cgats_1.queryv1("NUMBER_OF_SETS"):
        raise CGATS.CGATSInvalidError("Missing NUMBER_OF_SETS")
    if not cgats_1.queryv1("DATA_FORMAT"):
        raise CGATS.CGATSInvalidError("Missing DATA_FORMAT")
    for field in required:
        if field.encode("utf-8") not in list(cgats_1.queryv1("DATA_FORMAT").values()):
            raise CGATS.CGATSKeyError(f"Missing required field: {field}")
    if not ignore_unknown:
        for field in list(cgats_1.queryv1("DATA_FORMAT").values()):
            if field not in required:
                raise CGATS.CGATSError(f"Unknown field: {field}")
    modified = cgats_1.modified
    cgats_1.filename = cgats.filename
    cgats_1.modified = modified
    return cgats_1


def verify_ti1_rgb_xyz(cgats):
    """Verify and return a CGATS instance or None on failure.

    Verify if a CGATS instance has a TI1 section with all required fields
    for RGB devices. Return the TI1 section as CGATS instance on success,
    None on failure.
    """
    return verify_cgats(cgats, ("RGB_R", "RGB_B", "RGB_G", "XYZ_X", "XYZ_Y", "XYZ_Z"))
