"""Utilities for working with Argyll CMS CGATS files and calibration data.

It includes functions for manipulating CGATS data, extracting calibration
information, and creating or modifying ICC profiles with embedded calibration
data.
"""

from __future__ import annotations

# import decimal
# Decimal = decimal.Decimal
import contextlib
import decimal
import os
import traceback
from decimal import Decimal
from io import BytesIO
from time import strftime

from DisplayCAL import colormath
from DisplayCAL import localization as lang
from DisplayCAL.cgats import (
    CGATS,
    CGATSError,
    CGATSInvalidError,
    CGATSInvalidOperationError,
    CGATSKeyError,
    CGATSTypeError,
    CGATSValueError,
)
from DisplayCAL.debughelpers import Error
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileInvalidError,
    Text,
    TextDescriptionType,
    VideoCardGammaTableType,
    VideoCardGammaType,
    WcsProfilesTagType,
)
from DisplayCAL.options import DEBUG

CALS = {}


def quote_nonoption_args(args: list[str]) -> list[bytes]:
    """Put quotes around all arguments which are not options.

    (ie. which do not start with a hyphen '-')

    Args:
        args (list[str]): A list of arguments to be quoted.

    Returns:
        list[bytes]: A list of quoted arguments, where each argument that does not
            start with a hyphen is wrapped in quotes.
    """
    args = list(args)
    for i, arg in enumerate(args):
        # first convert everything to bytes
        if not isinstance(arg, bytes):
            arg = bytes(str(arg), "utf-8")
        args[i] = b'"%s"' % arg if arg[:1] != b"-" else arg
    return args


def add_dispcal_options_to_cal(cal: str | CGATS, options_dispcal: list[str]) -> CGATS:
    """Add dispcal options to cal.

    Args:
        cal (str | CGATS): The input CAL file or CGATS instance.
        options_dispcal (list[str]): List of dispcal options to add.

    Returns:
        CGATS: The modified CGATS instance with added options.
    """
    # Add dispcal options to cal
    options_dispcal = quote_nonoption_args(options_dispcal)
    try:
        cgats = CGATS(cal)
        cgats[0].add_section("ARGYLL_DISPCAL_ARGS", b" ".join(options_dispcal))
        return cgats
    except Exception:
        print(traceback.format_exc())


def add_options_to_ti3(
    ti3: str | CGATS,
    options_dispcal: None | list[str] = None,
    options_colprof: None | list[str] = None,
) -> CGATS:
    """Add dispcal and colprof options to ti3.

    Args:
        ti3 (str or CGATS): The input TI3 file or CGATS instance.
        options_dispcal (list): List of dispcal options to add.
        options_colprof (list): List of colprof options to add.

    Returns:
        CGATS: The modified CGATS instance with added options.
    """
    # Add dispcal and colprof options to ti3
    try:
        cgats = CGATS(ti3)
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


def cal_to_fake_profile(cal: str | CGATS) -> None | ICCProfile:
    """Create and return a 'fake' ICCProfile with just a vcgt tag.

    cal must refer to a valid Argyll CAL file and can be a CGATS instance
    or a filename.

    Args:
        cal (str | CGATS): The input CAL file or CGATS instance.

    Returns:
        None | ICCProfile: Returns an ICCProfile instance with a vcgt tag
            containing the calibration data, or None if the input is invalid
            or required fields are missing.
    """
    vcgt, cal = cal_to_vcgt(cal, True)
    if not vcgt:
        return None
    profile = ICCProfile()
    profile.fileName = cal.filename
    profile._data = b"\0" * 128
    profile._tags.desc = TextDescriptionType(b"", "desc")
    profile._tags.desc.ASCII = str(os.path.basename(cal.filename)).encode(
        "ascii", "asciize"
    )
    profile._tags.desc.Unicode = str(os.path.basename(cal.filename))
    profile._tags.vcgt = vcgt
    profile.size = len(profile.data)
    profile.is_loaded = True
    return profile


def cal_to_vcgt(
    cal: str | CGATS, return_cgats: bool = False
) -> None | VideoCardGammaTableType | tuple[VideoCardGammaTableType, CGATS]:
    """Create a vcgt tag from calibration data.

    cal must refer to a valid Argyll CAL file and can be a CGATS instance
    or a filename.

    Args:
        cal (str | CGATS): The input CAL file or CGATS instance.
        return_cgats (bool): If True, returns a tuple of
            VideoCardGammaTableType and CGATS instance. If False, returns only
            the VideoCardGammaTableType.

    Returns:
        None | VideoCardGammaTableType | tuple[VideoCardGammaTableType, CGATS]:
            Returns a VideoCardGammaTableType instance containing the `vcgt`
            data, or a tuple of VideoCardGammaTableType and CGATS instance if
            `return_cgats` is True. Returns None if the input is invalid or
            required fields are missing.
    """
    cal = validate_cgats(cal)
    required_fields = ("RGB_I", "RGB_R", "RGB_G", "RGB_B")
    if data_format := cal.queryv1("DATA_FORMAT"):
        for field in required_fields:
            if field.encode("utf-8") not in list(data_format.values()):
                if DEBUG:
                    print(f"[D] Missing required field: {field}")
                return None
        for field in list(data_format.values()):
            if field.decode("utf-8") not in required_fields:
                if DEBUG:
                    print(f"[D] Unknown field: {field}")
                return None
    entries = cal.queryv(required_fields)
    if len(entries) < 1:
        if DEBUG:
            print(f"[D] No entries found in calibration {cal.filename}")
        return None
    vcgt = VideoCardGammaTableType(b"", "vcgt")
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
    return vcgt, cal if return_cgats else vcgt


def validate_cgats(cal: str | CGATS) -> CGATS:
    """Validate and return a CGATS instance.

    Args:
        cal (str | CGATS): The input CAL file or CGATS instance.

    Returns:
        CGATS: A validated CGATS instance.
    """
    if not isinstance(cal, CGATS):
        try:
            cal = CGATS(cal)
        except (
            OSError,
            CGATSInvalidError,
            CGATSInvalidOperationError,
            CGATSKeyError,
            CGATSTypeError,
            CGATSValueError,
        ) as exception:
            print(f"Warning - couldn't process CGATS file '{cal}': {exception}")
            return None
    return cal


def can_update_cal(path: str) -> bool:
    """Check if cal can be updated by checking for required fields.

    Args:
        path (str): The path to the CGATS file.

    Returns:
        bool: True if the CGATS file can be updated, False otherwise.
    """
    try:
        calstat = os.stat(path)
    except Exception as exception:
        print(f"Warning - os.stat('{path}') failed: {exception}")
        return False
    if path not in CALS or CALS[path].mtime != calstat.st_mtime:
        try:
            cal = CGATS(path)
        except (
            OSError,
            CGATSInvalidError,
            CGATSInvalidOperationError,
            CGATSKeyError,
            CGATSTypeError,
            CGATSValueError,
        ) as exception:
            CALS.pop(path, None)
            print(f"Warning - couldn't process CGATS file '{path}': {exception}")
        else:
            if cal.queryv1("DEVICE_CLASS") == "DISPLAY" and None not in (
                cal.queryv1("TARGET_WHITE_XYZ"),
                cal.queryv1("TARGET_GAMMA"),
                cal.queryv1("BLACK_POINT_CORRECTION"),
                cal.queryv1("QUALITY"),
            ):
                CALS[path] = cal
    return path in CALS and CALS[path].mtime == calstat.st_mtime


def extract_cal_from_profile(
    profile: ICCProfile,
    out_cal_path: None | str = None,
    raise_on_missing_cal: bool = True,
    prefer_cal: bool = False,
) -> bool | CGATS:
    """Extract calibration from 'targ' tag in profile or vcgt as fallback.

    Args:
        profile (ICCProfile): The ICCProfile to extract the data from.
        out_cal_path (str, optional): If provided, the extracted calibration
            data will be saved to this path as a CGATS file.
        raise_on_missing_cal (bool): If True, raises an error if no calibration
            data is found in the profile. If False, returns False instead.
        prefer_cal (bool): If True, prefers the calibration data from the
            'targ' tag over the 'vcgt' tag, if both are present. If False,
            prefers the 'vcgt' tag if it is nonlinear.

    Raises:
        Error: If the calibration extraction fails or if no calibration data
            is found and `raise_on_missing_cal` is True.

    Returns:
        bool | CGATS: Returns a CGATS instance containing the calibration data
            if successful, or False if no calibration data is found and
            `raise_on_missing_cal` is False.
    """
    white = False

    # Check if calibration is included in TI3
    targ = profile.tags.get("targ", profile.tags.get("CIED"))
    cal = None
    if isinstance(targ, Text):
        cal = extract_cal_from_ti3(targ)
        if cal:
            check = cal
            cgats_builder = CGATS
            arg = cal

    if not cal:
        check, cgats_builder, arg = convert_cal_info_from_embedded_wcs_profile(profile)

    if check:
        try:
            cgats = cgats_builder(arg)
        except (OSError, CGATSError) as e:
            traceback.print_exc()
            raise Error(lang.getstr("cal_extraction_failed")) from e
    elif raise_on_missing_cal:
        raise Error(lang.getstr("profile.no_vcgt"))
    else:
        return False

    if (
        not cal
        or prefer_cal
        or not isinstance(profile.tags.get("vcgt"), VideoCardGammaType)
    ):
        if out_cal_path:
            cgats.write(out_cal_path)
        return cgats

    black, white = get_black_and_white_levels(cgats)
    cgats = vcgt_to_cal(profile)
    cgats = unscale_vcgt_from_video_levels(profile, cgats, black, white)
    if out_cal_path:
        cgats.write(out_cal_path)
    return cgats


def get_black_and_white_levels(cgats: CGATS) -> None | tuple[float, float]:
    """Get black and white levels for video encoding.

    Args:
        cgats (CGATS): The CGATS instance to query for black and white levels.

    Returns:
        tuple[float, float]: A tuple containing the black and white levels.
    """
    # When vcgt is nonlinear, prefer it
    # Check for video levels encoding
    black = None
    white = None
    if cgats.queryv1("TV_OUTPUT_ENCODING") == b"YES":
        black, white = (16, 235)
    elif output_enc := cgats.queryv1("OUTPUT_ENCODING"):
        try:
            black, white = (float(v) for v in output_enc.split())
        except (TypeError, ValueError):
            white = False

    return black, white


def convert_cal_info_from_embedded_wcs_profile(
    profile: ICCProfile,
) -> tuple[bool, callable, ICCProfile]:
    """Convert calibration info from embedded WCS profile to vcgt if missing.

    Args:
        profile (ICCProfile): The ICCProfile to extract the calibration data from.

    Returns:
        tuple[bool, callable, ICCProfile]: A tuple containing:
            - bool: True if the profile has a vcgt tag or can be converted to one,
            - callable: A function to convert the vcgt tag to calibration data,
            - ICCProfile: The ICCProfile instance with the vcgt tag.
    """
    if (
        isinstance(profile.tags.get("MS00"), WcsProfilesTagType)
        and "vcgt" not in profile.tags
    ):
        profile.tags["vcgt"] = profile.tags["MS00"].get_vcgt()

    # Get the calibration from profile vcgt
    check = isinstance(profile.tags.get("vcgt"), VideoCardGammaType)
    cgats_builder = vcgt_to_cal
    arg = profile
    return check, cgats_builder, arg


def unscale_vcgt_from_video_levels(
    profile: ICCProfile, cgats: CGATS, black: float, white: float
) -> CGATS:
    """Un-scale vcgt from video levels.

    Args:
        profile (ICCProfile): The ICC profile containing the vcgt tag.
        cgats (CGATS): The CGATS instance to apply scaling to.
        black (float): The black level for video encoding.
        white (float): The white level for video encoding.

    Returns:
        CGATS: The CGATS instance with applied video level scaling.
    """
    if not white or (black, white) == (0, 255):
        print(
            "No need to un-scale vcgt from video levels as black and white "
            f"levels are ({black}..{white})"
        )
        return cgats
    print(f"Need to un-scale vcgt from video levels ({black}..{white})")

    # Need to un-scale video levels
    data = cgats.queryv1("DATA")
    if not data:
        print("Warning - no un-scaling applied - no calibration data!")
        return cgats

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
    return cgats


def extract_cal_from_ti3(ti3: str | BytesIO) -> bytes:
    """Extract and return the CAL section of a TI3.

    ti3 can be a file object or a string holding the data.

    Returns:
        bytes: The extracted data.
    """
    if isinstance(ti3, CGATS):
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
    with contextlib.suppress(AttributeError):
        ti3.close()

    return b"\n".join(cal_lines)


def extract_fix_copy_cal(
    source_filename: str, target_filename: None | str = None
) -> None | list[str] | Exception:
    """Return the CAL section from a profile's embedded measurement data.

    Try to 'fix it' (add information needed to make the resulting .cal file
    'updatable') and optionally copy it to target_filename.

    Args:
        source_filename (str): The path to the source profile file.
        target_filename (str, optional): The path to save the fixed CAL data.
            If None, the data is not saved to a file.

    Returns:
        None | list[str] | Exception: Returns a list of CAL lines if found and
            None if not and Exception if any exception is raised.
    """
    from DisplayCAL.worker import get_options_from_profile

    try:
        profile = ICCProfile(source_filename)
    except (OSError, ICCProfileInvalidError) as exception:
        return exception
    if "CIED" not in profile.tags and "targ" not in profile.tags:
        return None
    cal_lines = []
    with BytesIO(profile.tags.get("CIED", b"") or profile.tags.get("targ", b"")) as ti3:
        ti3_lines = [line.strip() for line in ti3]

    cal_found = False
    for line in ti3_lines:
        cal_found = line == b"CAL"
        # Make sure CGATS file identifiers are always a minimum of 7 characters long
        line = line.ljust(7) if cal_found else line
        if not cal_found or line != b'DEVICE_CLASS "DISPLAY"':
            continue
        options_dispcal = get_options_from_profile(profile)[0]
        if not options_dispcal:
            continue
        cal_lines.append(line)
        # b = profile.tags.lumi.Y
        cal_lines = build_cal_from_profile(cal_lines, options_dispcal)

    if cal_lines:
        if target_filename:
            try:
                with open(target_filename, "wb") as f:
                    f.write(b"\n".join(cal_lines))
            except Exception as exception:
                return exception
        return cal_lines
    return None


def build_cal_from_profile(
    cal_lines: list[bytes], options_dispcal: list
) -> list[bytes]:
    """Build a CAL section from profile options.

    Args:
        cal_lines (list[bytes]): The list to append CAL lines to.
        options_dispcal (list): List of dispcal options to add to the CAL section.
    """
    whitepoint = False
    for option in options_dispcal:
        if option[0] == b"y":
            cal_lines.extend(
                [
                    b'KEYWORD "DEVICE_TYPE"',
                    {b"c": b'DEVICE_TYPE "CRT"'}.get(option[1], b'DEVICE_TYPE "LCD"'),
                ]
            )
            continue
        if option[0] in (b"t", b"T", b"w"):
            continue
        if option[0] in (b"g", b"G"):
            trc = {
                b"240": b"SMPTE240M",
                b"709": b"REC709",
                b"l": b"L_STAR",
                b"s": b"sRGB",
            }.get(option[1:], option[1:])
            if trc == option[1:] and option[0] == b"G":
                try:
                    trc = 0 - Decimal(trc)
                except decimal.InvalidOperation:
                    continue
            cal_lines.extend((b'KEYWORD "TARGET_GAMMA"', b'TARGET_GAMMA "%s"' % trc))
            continue

        to_extend = {
            b"f": (
                b'KEYWORD "DEGREE_OF_BLACK_OUTPUT_OFFSET"',
                b'DEGREE_OF_BLACK_OUTPUT_OFFSET "%s"' % option[1:],
            ),
            b"k": (
                b'KEYWORD "BLACK_POINT_CORRECTION"',
                b'BLACK_POINT_CORRECTION "%s"' % option[1:],
            ),
            b"B": (
                b'KEYWORD "TARGET_BLACK_BRIGHTNESS"',
                b'TARGET_BLACK_BRIGHTNESS "%s"' % option[1:],
            ),
        }.get(option[0:1], None)
        if to_extend:
            cal_lines.extend(to_extend)
            continue

        if option[0] == b"q":
            q = {
                b"l": b"low",
                b"m": b"medium",
            }.get(option[1:2], b"high")
            cal_lines.extend((b'KEYWORD "QUALITY"', b'QUALITY "%s"' % q))
    cal_lines.extend(
        (
            b'KEYWORD "NATIVE_TARGET_WHITE"',
            b'NATIVE_TARGET_WHITE ""',
        )
        if not whitepoint
        else ()
    )
    return cal_lines


def extract_device_gray_primaries(
    ti3: CGATS,
    gray: bool = True,
    logfn: None | bool = None,
    include_neutrals: bool = False,
    neutrals_ab_threshold: float = 0.1,
) -> tuple[CGATS, dict, dict]:
    """Extract gray or primaries into new TI3.

    Args:
        ti3 (CGATS): The CGATS instance containing the TI3 data.
        gray (bool): If True, extract gray neutrals, otherwise extract RGB primaries.
        logfn (callable): A logging function to call with messages.
        include_neutrals (bool): If True, include neutral readings in the extraction.
        neutrals_ab_threshold (float): Threshold for neutral readings in Lab space.

    Returns:
        tuple: A tuple containing:
            - CGATS: The extracted TI3 data.
            - dict: A mapping of extracted RGB to XYZ values.
            - dict: A mapping of remaining RGB to XYZ values.
    """
    filename = ti3.filename
    ti3 = ti3.queryi1("DATA")
    ti3.filename = filename
    ti3_extracted = CGATS(
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

    ti3_extracted, rgb_xyz_extracted, rgb_xyz_remaining, dupes = extract_rgb_xyz_data(
        ti3,
        gray,
        include_neutrals,
        neutrals_ab_threshold,
        ti3_extracted,
        subset,
    )

    for rgb, count in dupes.items():
        for rgb_xyz in (rgb_xyz_extracted, rgb_xyz_remaining):
            if rgb in rgb_xyz:
                # Average values
                xyz = tuple(rgb_xyz[rgb][i] / count for i in range(3))
                rgb_xyz[rgb] = xyz
    return ti3_extracted, rgb_xyz_extracted, rgb_xyz_remaining


def extract_rgb_xyz_data(
    ti3: CGATS,
    gray: bool,
    include_neutrals: bool,
    neutrals_ab_threshold: float,
    ti3_extracted: CGATS,
    subset: list[tuple[float, float, float]],
) -> CGATS:
    """Extract RGB and XYZ data from TI3.

    Args:
        ti3 (CGATS): The CGATS instance containing the TI3 data.
        gray (bool): If True, extract gray neutrals, otherwise extract RGB primaries.
        include_neutrals (bool): If True, include neutral readings in the extraction.
        neutrals_ab_threshold (float): Threshold for neutral readings in Lab space.
        ti3_extracted (CGATS): The CGATS instance to store extracted data.
        subset (list): List of RGB values to be included in the extraction.

    Raises:
        Error: If required fields are missing in the TI3 data.

    Returns:
        tuple[CGATS, dict, dict, dict]: The CGATS instance containing the
            extracted data, the dictionary of extracted RGB to XYZ mappings,
            the dictionary of remaining RGB to XYZ mappings, and the dictionary
            of duplicate RGB values.
    """
    rgb_xyz_extracted = {}
    rgb_xyz_remaining = {}
    dupes = {}

    if include_neutrals:
        white = ti3.get_white_cie("XYZ")
        str_thresh = str(neutrals_ab_threshold)
        round_digits = len(str_thresh[str_thresh.find(".") + 1 :])

    for i in ti3.DATA:
        item = ti3.DATA[i]
        if not i:  # don't validate the header
            validate_ti3_item(ti3, item)
        rgb = (item["RGB_R"], item["RGB_G"], item["RGB_B"])
        xyz = (item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"])
        for rgb_xyz in (rgb_xyz_extracted, rgb_xyz_remaining):
            if rgb not in rgb_xyz:
                continue
            if rgb != (100.0, 100.0, 100.0):
                # Add to existing values for averaging later
                # if it's not white (all other readings are scaled to the
                # white Y by dispread, so we don't alter it. Note that it's
                # always the first encountered white that will have Y = 100,
                # even if subsequent white readings may be higher)
                xyz = tuple(rgb_xyz[rgb][i] + xyz[i] for i in range(3))
                if rgb not in dupes:
                    dupes[rgb] = 1.0
                dupes[rgb] += 1.0
            elif rgb in subset:
                # We have white already, remove it from the subset so any
                # additional white readings we encounter are ignored
                subset.remove(rgb)
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
            and rgb not in [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
        ) or rgb in subset:
            ti3_extracted.DATA.add_data(item)
            rgb_xyz_extracted[rgb] = xyz
        elif rgb not in [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]:
            rgb_xyz_remaining[rgb] = xyz

    return ti3_extracted, rgb_xyz_extracted, rgb_xyz_remaining, dupes


def validate_ti3_item(ti3: CGATS, item: dict) -> None:
    """Validate a TI3 item to ensure it contains required fields.

    Args:
        ti3 (CGATS): The CGATS instance containing the TI3 data.
        item (dict): The TI3 item to validate.

    Raises:
        Error: If required fields are missing in the TI3 item.
    """
    # Check if fields are missing
    required_fields = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
    for field in required_fields:
        if field not in item:
            lang.getstr("error.testchart.missing_fields", (ti3.filename, field))


def ti3_to_ti1(ti3_data: str | list[str] | BytesIO) -> bytes:
    """Create and return TI1 data converted from TI3.

    Args:
        ti3_data (str | list[str] | BytesIO): Can be a file object, a list of
            strings or a string holding the data.

    Returns:
        bytes: The converted TI1 data as bytes.
    """
    ti3 = CGATS(ti3_data)
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


def vcgt_to_cal(profile: ICCProfile) -> CGATS:
    """Return a CAL (CGATS instance) from vcgt.

    Args:
        profile (ICCProfile): The ICC profile containing the vcgt tag.

    Returns:
        CGATS: A CGATS instance representing the calibration data.
    """
    cgats = CGATS(file_identifier=b"CAL")
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
    context[key] = CGATS()
    context[key].key = key
    context[key].parent = context
    context[key].root = cgats
    context[key].type = key.encode("utf-8")
    context[key].add_data((b"RGB_I", b"RGB_R", b"RGB_G", b"RGB_B"))
    key = "DATA"
    context[key] = CGATS()
    context[key].key = key
    context[key].parent = context
    context[key].root = cgats
    context[key].type = key.encode("utf-8")
    values = profile.tags.vcgt.getNormalizedValues()
    for i, triplet in enumerate(values):
        context[key].add_data((b"%.7f" % (i / float(len(values) - 1)), *triplet))
    return cgats


def verify_cgats(
    cgats: CGATS, required: tuple[str], ignore_unknown: bool = True
) -> CGATS:
    """Verify and return a CGATS instance or None on failure.

    Verify if a CGATS instance has a section with all required fields.
    Return the section as CGATS instance on success, None on failure.

    If ignore_unknown evaluates to True, ignore fields which are not required.
    Otherwise, the CGATS data must contain only the required fields, no more,
    no less.

    Args:
        cgats (CGATS): The CGATS instance to verify.
        required (tuple[str]): A tuple of required field names.
        ignore_unknown (bool): Whether to ignore unknown fields.

    Raises:
        CGATSKeyError: If a required field is missing.
        CGATSInvalidError: If the CGATS data is invalid or incomplete.
        CGATSError: If an unknown field is found and ignore_unknown is False.

    Returns:
        CGATS: The verified CGATS instance containing the required section,
            or raises an error if verification fails.
    """
    cgats_1 = cgats.queryi1(required)
    if not cgats_1 or not cgats_1.parent or not cgats_1.parent.parent:
        raise CGATSKeyError(f"Missing required fields: {', '.join(required)}")
    cgats_1 = cgats_1.parent.parent
    if not cgats_1.queryv1("NUMBER_OF_SETS"):
        raise CGATSInvalidError("Missing NUMBER_OF_SETS")
    if not cgats_1.queryv1("DATA_FORMAT"):
        raise CGATSInvalidError("Missing DATA_FORMAT")
    for field in required:
        if field.encode("utf-8") not in list(cgats_1.queryv1("DATA_FORMAT").values()):
            raise CGATSKeyError(f"Missing required field: {field}")
    if not ignore_unknown:
        for field in list(cgats_1.queryv1("DATA_FORMAT").values()):
            if field not in required:
                raise CGATSError(f"Unknown field: {field}")
    modified = cgats_1.modified
    cgats_1.filename = cgats.filename
    cgats_1.modified = modified
    return cgats_1


def verify_ti1_rgb_xyz(cgats: CGATS) -> None | CGATS:
    """Verify and return a CGATS instance or None on failure.

    Verify if a CGATS instance has a TI1 section with all required fields
    for RGB devices. Return the TI1 section as CGATS instance on success,
    None on failure.

    Args:
        cgats (CGATS): The CGATS instance to verify.

    Returns:
        None | CGATS: The verified CGATS instance containing the TI1 section, or None
            if verification fails.
    """
    return verify_cgats(cgats, ("RGB_R", "RGB_B", "RGB_G", "XYZ_X", "XYZ_Y", "XYZ_Z"))
