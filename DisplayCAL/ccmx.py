"""Convert iColorDisplay DeviceCorrections.txt to Argyll CCMX files.

It parses the input file, extracts relevant data, and generates CCMX files in
the specified format for use with color calibration tools.
"""

import math
import os
import re
import sys
import time

from DisplayCAL.util_str import make_filename_safe

CCMX_TEMPLATE = """CCMX

DESCRIPTOR "%(Name)s"
KEYWORD "INSTRUMENT"
INSTRUMENT "%(Device)s"
KEYWORD "DISPLAY"
DISPLAY "%(Display)s"
KEYWORD "DISPLAY_TYPE_BASE_ID"
DISPLAY_TYPE_BASE_ID "1"
KEYWORD "REFERENCE"
REFERENCE "%(ReferenceDevice)s"
ORIGINATOR "%(Originator)s"
CREATED "%(DateTime)s"
KEYWORD "COLOR_REP"
COLOR_REP "XYZ"

NUMBER_OF_FIELDS 3
BEGIN_DATA_FORMAT
XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
%(MatrixXYZ)s
END_DATA
"""

#: Filename stems Windows reserves for devices, regardless of extension.
WINDOWS_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)

#: Longest filename stem we generate, well below the usual 255 byte limit.
MAX_FILENAME_STEM_LENGTH = 200


class DeviceCorrectionsError(Exception):
    """Raised when a DeviceCorrections.txt file can't be parsed."""


def read_devicecorrections_text(path: str) -> str:
    """Read DeviceCorrections.txt, tolerating a UTF-8 BOM or a legacy codepage.

    iColorDisplay is Windows software, so the file may be UTF-8 with or without
    a BOM, or encoded in the Windows ANSI codepage.

    Args:
        path (str): Path to the DeviceCorrections.txt file.

    Returns:
        str: The decoded file contents.
    """
    with open(path, "rb") as devcorrections_file:
        data = devcorrections_file.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def unquote(value: str) -> str:
    """Strip one pair of surrounding double quotes from a value, if present.

    Args:
        value (str): The (already whitespace stripped) value.

    Returns:
        str: The unquoted value.
    """
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse_devicecorrections(text: str) -> list[tuple[str, dict[str, str]]]:
    """Parse the contents of an iColorDisplay DeviceCorrections.txt file.

    The DeviceCorrections.txt format is as follows:

        "Description here, e.g. Instrument X for Monitor Y" =
        {
          Name = "Description here, e.g. Instrument X for Monitor Y"
          Device = "Instrument X"
          Display = "Monitor Y"
          ReferenceDevice = "eye-one Pro Rev.D"
          MatrixXYZ = "3 3 1482250784 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0 "
        }
        "Description here, e.g. Instrument X for Monitor Y" =
        {
          ...
        }
        ...etc.

    Values are taken verbatim between the outer quotes, so they may contain
    ``=``, quotes or backslashes.

    Args:
        text (str): The file contents.

    Raises:
        DeviceCorrectionsError: If the text doesn't follow the format above.

    Returns:
        list[tuple[str, dict[str, str]]]: The entries in file order as
            ``(name, fields)`` tuples. Duplicate names are kept.
    """
    entries = []
    name = None
    fields = None
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if fields is not None:
            # Inside an entry block
            if line == "}":
                entries.append((name, fields))
                name = fields = None
                continue
            key, sep, value = line.partition("=")
            key = key.strip()
            if not sep or not key:
                raise DeviceCorrectionsError(
                    f"Line {line_num}: expected 'Key = \"Value\"', got {line!r}"
                )
            fields[key] = unquote(value.strip())
        elif line == "{":
            if name is None:
                raise DeviceCorrectionsError(
                    f"Line {line_num}: entry block without a name"
                )
            fields = {}
        elif line.endswith("{") and line[:-1].rstrip().endswith("="):
            # Name and opening brace on the same line
            name = unquote(line[:-1].rstrip()[:-1].strip())
            fields = {}
        elif line.endswith("=") and name is None:
            name = unquote(line[:-1].strip())
        else:
            raise DeviceCorrectionsError(f"Line {line_num}: unexpected {line!r}")
    if name is not None:
        raise DeviceCorrectionsError(f"Entry {name!r} is not terminated")
    return entries


def parse_matrix(value: str) -> list[str] | None:
    """Return the nine matrix numbers from a MatrixXYZ value.

    The first three numbers are irrelevant for our purposes (see the format
    example in :func:`parse_devicecorrections`).

    Args:
        value (str): The MatrixXYZ value.

    Returns:
        list[str] | None: The nine numbers as written in the file, or None if
            the value doesn't hold exactly nine finite numbers after the first
            three.
    """
    matrix = value.split()[3:]
    if len(matrix) != 9:
        return None
    try:
        if not all(math.isfinite(float(number)) for number in matrix):
            return None
    except ValueError:
        return None
    return matrix


def quote_cgats_string(value: str) -> str:
    """Escape a value for use inside a quoted CGATS string.

    Embedded double quotes are doubled, like Argyll's own CGATS writer does.

    Args:
        value (str): The value to escape.

    Returns:
        str: The escaped value, without the surrounding quotes.
    """
    return value.replace('"', '""')


def make_ccmx_filename_stem(name: str) -> str:
    """Turn an entry name into a filename stem that is safe on every OS.

    Path separators and characters invalid on Windows are replaced, so the
    resulting file always lands directly inside the target directory.

    Args:
        name (str): The entry name from DeviceCorrections.txt.

    Returns:
        str: The filename stem, without extension.
    """
    stem = make_filename_safe(re.sub(r"[\x00-\x1f\x7f]", "_", name))
    # Windows strips trailing dots and spaces, leading dots hide files on Unix
    stem = stem[:MAX_FILENAME_STEM_LENGTH].strip(" .")
    if not stem:
        return "iColorDisplay"
    if stem.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    return stem


def strip_created_line(ccmx_text: str) -> str:
    """Remove the CREATED line, which differs on every conversion.

    Args:
        ccmx_text (str): The CCMX file contents.

    Returns:
        str: The contents without the CREATED line.
    """
    return re.sub(r"^CREATED .*$", "", ccmx_text, flags=re.MULTILINE)


def write_ccmx(target_dir: str, stem: str, ccmx_text: str, written: set) -> None:
    """Write a CCMX file without clobbering unrelated existing files.

    If ``<stem>.ccmx`` already exists with the same correction (e.g. on
    re-import), it is left alone. If it holds a different correction, or was
    already written by this import (duplicate entry names), a numbered name
    like ``<stem> (2).ccmx`` is used instead.

    Args:
        target_dir (str): Directory to write the file to.
        stem (str): The safe filename stem.
        ccmx_text (str): The CCMX file contents.
        written (set): Paths written so far by this import, updated in place.
    """
    counter = 1
    filename = f"{stem}.ccmx"
    while True:
        path = os.path.join(target_dir, filename)
        if path in written:
            pass
        elif not os.path.exists(path):
            break
        else:
            try:
                with open(path, encoding="utf-8") as existing_file:
                    existing = existing_file.read()
            except (OSError, UnicodeDecodeError):
                existing = None
            if existing is not None and strip_created_line(
                existing
            ) == strip_created_line(ccmx_text):
                written.add(path)
                return
        counter += 1
        filename = f"{stem} ({counter}).ccmx"
    with open(path, "w", encoding="utf-8") as ccmx:
        ccmx.write(ccmx_text)
    written.add(path)


def convert_devicecorrections_to_ccmx(path: str, target_dir: str) -> tuple[int, int]:
    """Convert iColorDisplay DeviceCorrections.txt to individual Argyll CCMX files.

    Args:
        path (str): Path to the DeviceCorrections.txt file.
        target_dir (str): Directory where the generated CCMX files will be saved.

    Raises:
        DeviceCorrectionsError: If the file can't be parsed.

    Returns:
        tuple[int, int]: A tuple containing the number of imported and skipped
            entries.
    """
    entries = parse_devicecorrections(read_devicecorrections_text(path))
    imported = 0
    skipped = 0
    written = set()
    for name, devcorrection in entries:
        values = {
            "DateTime": time.strftime("%a %b %d %H:%M:%S %Y"),
            "Originator": "Quato iColorDisplay",
            "Name": quote_cgats_string(
                "{} & {}".format(
                    devcorrection.get("Device"), devcorrection.get("Display")
                )
            ),
        }
        for key in ("Device", "Display", "ReferenceDevice", "MatrixXYZ"):
            value = devcorrection.get(key)
            if value is None:
                break
            if key == "MatrixXYZ":
                matrix = parse_matrix(value)
                if matrix is None:
                    value = None
                    break
                value = "\n".join(
                    [" ".join(part) for part in (matrix[0:3], matrix[3:6], matrix[6:9])]
                )
            else:
                value = quote_cgats_string(value)
            values[key] = value
        if value is None:
            skipped += 1
            continue
        write_ccmx(
            target_dir, make_ccmx_filename_stem(name), CCMX_TEMPLATE % values, written
        )
        imported += 1
    return imported, skipped


if __name__ == "__main__":
    convert_devicecorrections_to_ccmx(sys.argv[1], os.path.dirname(sys.argv[1]))
