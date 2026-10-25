"""Simple CGATS file parser class.

Copyright (C) 2008 Florian Hoech
"""

from __future__ import annotations

import functools
import io
import math
import os
import re
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, BinaryIO, Callable

from DisplayCAL import colormath
from DisplayCAL.colorspace_to_vrml import COLORSPACE_NAME_TO_VRML_MAP, ColorSpaceToVRML
from DisplayCAL.icc_profile import ICCProfileTag
from DisplayCAL.log import safe_print
from DisplayCAL.options import DEBUG


def debug_print(*args, other_conditions: bool = True) -> None:
    """Print debug messages if DEBUG is enabled and other conditions are met.

    Args:
        *args: The arguments to print.
        other_conditions (bool): Additional conditions to check before printing.
            Defaults to True.
    """
    if DEBUG and other_conditions:
        print(*args)


# Non-finite spellings of the MSVC C runtime, which Argyll's Windows builds
# write into .ti3 files but Python's float() rejects: "-nan(ind)",
# "nan(snan)" (UCRT) and "1.#QNAN", "1.#IND", "1.#INF" (pre-UCRT).
MSVC_NAN_RE = re.compile(rb"^[+-]?(?:nan\(\w*\)|1\.#(?:QNAN|SNAN|IND)\d*)$", re.I)
MSVC_INF_RE = re.compile(rb"^([+-]?)1\.#INF\d*$", re.I)


def parse_float(value: bytes | str | float) -> float:
    """Convert a CGATS value to float, accepting MSVC NaN/inf spellings.

    Args:
        value (bytes | str | float): The value to convert.

    Raises:
        ValueError: If the value can not be converted to float.

    Returns:
        float: The converted value.
    """
    if isinstance(value, (bytes, str)):
        bvalue = value.encode() if isinstance(value, str) else value
        bvalue = bvalue.strip()
        if MSVC_NAN_RE.match(bvalue):
            return math.nan
        match = MSVC_INF_RE.match(bvalue)
        if match:
            return -math.inf if match.group(1) == b"-" else math.inf
    return float(value)


def get_device_value_labels(color_rep: None | str = None) -> list[bytes]:
    """Return a list of device value labels.

    Args:
        color_rep (None | str): Color representation. Default is None.

    Returns:
        list: List of device value labels.
    """
    # TODO: Avoid using filter...
    return list(
        filter(
            bool,
            [
                v[1] if not color_rep or v[0] == color_rep else False
                for v in {
                    b"CMYK": (b"CMYK_C", b"CMYK_M", b"CMYK_Y", b"CMYK_K"),
                    b"RGB": (b"RGB_R", b"RGB_G", b"RGB_B"),
                }
            ],
        )
    )


def rpad(value: int | float | complex | str, width: int) -> bytes:  # noqa: PYI041
    """If value isn't a number, return a quoted string representation.

    If value is greater or equal than 1e+16, return string in scientific
    notation. Otherwise, return string in decimal notation right-padded to
    given width (using trailing zeros).

    Args:
        value (int | float | complex | str): The value to format.
        width (int): The width to pad the string to.
    """
    strval = b""
    if not isinstance(value, bytes):
        strval = bytes(str(value), "UTF-8")

    if not isinstance(value, (int, float, complex)):
        # Return quoted string representation
        # Also need to escape single quote -> double quote
        return b'"%s"' % strval.replace(b'"', b'""')

    if value < 1e16:
        i = strval.find(b".")
        if i > -1:
            if i < width - 1:
                # Avoid scientific notation by formatting to decimal
                fmt = b"%%%i.%if" % (width, width - i - 1)
                strval = fmt % value
            else:
                strval = bytes(str(round(value)), "UTF-8")
    return strval


def sort_rgb_gray_to_top(a: tuple, b: tuple) -> int:
    """Sort RGB values to the top.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    if a[0] == a[1] == a[2]:
        if b[0] == b[1] == b[2]:
            return 0
        return -1
    return 0


def sort_rgb_to_top_factory(i1: int, i2: int, i3: int, i4: int) -> Callable:
    """Return a function to sort RGB values to the top.

    Args:
        i1 (int): Index of the first RGB value.
        i2 (int): Index of the second RGB value.
        i3 (int): Index of the third RGB value.
        i4 (int): Index of the fourth RGB value.

    Returns:
        function: A function that sorts two RGB tuples by their values.
    """

    def sort_rgb_to_top(
        a: tuple[float, float, float], b: tuple[float, float, float]
    ) -> int:
        """Sort two RGB tuples by their values.

        Args:
            a (tuple[float, float, float]): First RGB tuple.
            b (tuple[float, float, float]): Second RGB tuple.

        Returns:
            int: 1 if a > b, -1 if a < b, 0 if equal.
        """
        if a[i1] == a[i2] and 0 <= a[i3] < a[i4]:
            if b[i1] == b[i2] and 0 <= b[i3] < b[i4]:
                return 0
            return -1
        return 0

    return sort_rgb_to_top


def sort_rgb_white_to_top(a: tuple, b: tuple) -> int:
    """Sort RGB values to the top.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    sum1 = sum(a[:3])
    # sum2 = sum(b[:3])
    return -1 if sum1 == 300 else 0


def sort_by_hsi(a: tuple, b: tuple) -> int:
    """Sort by HSI value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    a = list(colormath.RGB2HSI(*a[:3]))
    b = list(colormath.RGB2HSI(*b[:3]))
    a[0] = round(math.degrees(a[0]))
    b[0] = round(math.degrees(b[0]))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def sort_by_hsl(a: tuple, b: tuple) -> int:
    """Sort by HSL value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    a = list(colormath.RGB2HSL(*a[:3]))
    b = list(colormath.RGB2HSL(*b[:3]))
    a[0] = round(math.degrees(a[0]))
    b[0] = round(math.degrees(b[0]))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def sort_by_hsv(a: tuple, b: tuple) -> int:
    """Sort by HSV value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    a = list(colormath.RGB2HSV(*a[:3]))
    b = list(colormath.RGB2HSV(*b[:3]))
    a[0] = round(math.degrees(a[0]))
    b[0] = round(math.degrees(b[0]))
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def sort_by_rgb(a: tuple, b: tuple) -> int:
    """Sort by RGB value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    if a[:3] > b[:3]:
        return 1
    if a[:3] < b[:3]:
        return -1
    return 0


def sort_by_bgr(a: tuple, b: tuple) -> int:
    """Sort by BGR value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    if a[:3][::-1] > b[:3][::-1]:
        return 1
    if a[:3] == b[:3]:
        return 0
    return -1


def sort_by_rgb_sum(a: tuple, b: tuple) -> int:
    """Sort by RGB sum.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    sum1, sum2 = sum(a[:3]), sum(b[:3])
    if sum1 > sum2:
        return 1
    if sum1 < sum2:
        return -1
    return 0


def sort_by_rgb_pow_sum(a: tuple, b: tuple) -> int:
    """Sort by RGB power sum.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    sum1, sum2 = sum(v**2.2 for v in a[:3]), sum(v**2.2 for v in b[:3])
    if sum1 > sum2:
        return 1
    if sum1 < sum2:
        return -1
    return 0


def stable_sort_by_l(a: tuple, b: tuple) -> int:
    """Stable sort by L* value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """
    return sort_by_l(a, b, stable=True)


def sort_by_l(a: tuple, b: tuple, stable: bool = False) -> int:
    """Sort by L* value.

    Args:
        a (tuple): First RGB tuple.
        b (tuple): Second RGB tuple.
        stable (bool): If True, sort stably by L* value.

    Returns:
        int: 1 if a > b, -1 if a < b, 0 if equal.
    """

    def sort(a1: float, b1: float) -> int:
        """Compare two L* values.

        Args:
            a1 (float): First L* value.
            b1 (float): Second L* value.

        Returns:
            int: 1 if a1 > b1, -1 if a1 < b1, 0 if equal.
        """
        if a1 > b1:
            return 1
        if a1 < b1:
            return -1
        return 0

    lab1 = colormath.XYZ2Lab(*a[3:])
    lab2 = colormath.XYZ2Lab(*b[3:])
    if stable:
        for i in range(len(lab1)):
            v = sort(lab1[i], lab2[i])
            if v != 0:
                return v
        return 0
    return sort(lab1[0], lab2[0])


def sort_by_luma_factory(ry: float, gy: float, by: float, gamma: float = 1) -> Callable:
    """Return a function to sort by luma.

    Args:
        ry (float): Red Y value.
        gy (float): Green Y value.
        by (float): Blue Y value.
        gamma (float): Gamma correction value. Default is 1.

    Returns:
        function: A function that sorts two RGB tuples by their luma value.
    """

    def sort_by_luma(
        a: tuple[float, float, float], b: tuple[float, float, float]
    ) -> int:
        """Sort two RGB tuples by their luma value.

        Args:
            a (tupltuple[float, float, float]e): First RGB tuple.
            b (tuple[float, float, float]): Second RGB tuple.

        Returns:
            int: 1 if a > b, -1 if a < b, 0 if equal.
        """
        a = ry * a[0] ** gamma + gy * a[1] ** gamma + by * a[2] ** gamma
        b = ry * b[0] ** gamma + gy * b[1] ** gamma + by * b[2] ** gamma
        if a > b:
            return 1
        if a < b:
            return -1
        return 0

    return sort_by_luma


sort_by_rec709_luma = sort_by_luma_factory(0.2126, 0.7152, 0.0722)


class CGATSError(Exception):
    """Base class for CGATS errors."""


class CGATSInvalidError(CGATSError, IOError):
    """Invalid CGATS file error."""


class CGATSInvalidOperationError(CGATSError):
    """Invalid operation error."""


class CGATSKeyError(CGATSError, KeyError):
    """CGATS key not found error."""


class CGATSTypeError(CGATSError, TypeError):
    """CGATS type error."""


class CGATSValueError(CGATSError, ValueError):
    """CGATS value error."""


class CGATS(MutableMapping):
    """CGATS structure.

    CGATS files are treated mostly as 'soup', so only basic checking is in place.

    Backed by a private ``_data`` dict rather than subclassing dict directly.

    Args:
        cgats (None | str | bytes | list | Path | io.IOBase | ICCProfileTag, optional):
            Can be a path, a string holding CGATS data, or a file object.
        normalize_fields (bool, optional): If True, convert all KEYWORDs and
            all fields in DATA_FORMAT to UPPERCASE and SampleId or SampleName
            to SAMPLE_ID or SAMPLE_NAME respectively. Defaults to False.
        file_identifier (bytes, optional): The file identifier to use. Defaults
            to b"CTI3". It is used as fallback if no file identifier is
            present.
        emit_keywords (bool, optional): If True, emit KEYWORDs in the output.
            Defaults to False.
        strict (bool, optional): If True, raise errors for malformed data.
            Defaults to False.
    """

    datetime = None
    filename = None
    key = None
    _lvl = 0
    _modified = False
    mtime = None
    parent = None
    root = None
    type = b"ROOT"
    vmaxlen = 0

    def __init__(
        self,
        cgats: None | str | bytes | list | Path | io.IOBase | ICCProfileTag = None,
        normalize_fields: bool = False,
        file_identifier: bytes = b"CTI3",
        emit_keywords: bool = False,
        strict: bool = False,
    ) -> None:
        object.__setattr__(self, "_data", {})
        super().__init__()

        self.normalize_fields = normalize_fields
        self.file_identifier = file_identifier.strip()
        self.emit_keywords = emit_keywords
        self.root = self

        if not cgats:
            return

        raw_lines = self.read_raw_data(cgats)

        if self.filename:
            self.mtime = os.stat(self.filename).st_mtime

        self.parse_raw_data(strict, raw_lines)

    def read_raw_data(self, cgats: str | bytes | list | Path | io.IOBase) -> list:
        """Read raw CGATS data.

        Args:
            cgats (str | bytes | list | Path | io.IOBase): CGATS data to parse.

        Raises:
            CGATSInvalidError: If the type of cgats is unsupported.

        Returns:
            list: Parsed CGATS data lines.
        """
        raw_lines = []
        if isinstance(cgats, list):
            raw_lines = cgats
        elif isinstance(cgats, str):
            if "\n" not in cgats or "\r" not in cgats:
                # assume filename
                with open(cgats, "rb") as cgats_:
                    self.filename = cgats_.name
                    cgats_.seek(0)
                    raw_lines = cgats_.readlines()
            else:
                # assume text
                with io.StringIO(cgats) as cgats_:
                    cgats_.seek(0)
                    raw_lines = cgats_.readlines()
        elif isinstance(cgats, bytes):
            # assume text
            with io.BytesIO(cgats) as cgats_:
                cgats_.seek(0)
                raw_lines = cgats_.readlines()
        elif isinstance(cgats, ICCProfileTag):
            with io.BytesIO(cgats.tagData) as cgats_:
                cgats_.seek(0)
                raw_lines = cgats_.readlines()
        elif isinstance(cgats, Path):
            self.filename = cgats.absolute()
            with open(cgats, "rb") as cgats_:
                cgats_.seek(0)
                raw_lines = cgats_.readlines()
        elif isinstance(cgats, io.IOBase):
            if hasattr(cgats, "readlines"):
                cgats.seek(0)
                raw_lines = cgats.readlines()
            else:
                # Assume file-like object
                raw_lines = cgats.read()
                if isinstance(raw_lines, bytes):
                    raw_lines = [raw_lines]
            cgats.close()
        else:
            raise CGATSInvalidError(f"Unsupported type: {type(cgats)}")
        return raw_lines

    def parse_raw_data(self, strict: bool, raw_lines: list) -> None:
        """Parse raw CGATS data.

        Args:
            strict (bool): If True, raise errors for malformed data.
            raw_lines (list): List of raw CGATS data lines to parse.

        Raises:
            CGATSInvalidError: If strict is True and data is malformed.

        """
        context = self
        for raw_line in raw_lines:
            # Replace 1.#IND00 with NaN
            raw_line = raw_line.replace(b"1.#IND00", b"NaN")

            # strip control chars and leading/trailing whitespace
            line = re.sub(b"[^\x09\x20-\x7e\x80-\xff]", b"", raw_line.strip())
            line, values = self._parse_raw_data_deal_with_quotes(line)
            context = self._parse_raw_data_begin(context, line)
            context = self._parse_data_begin_and_end(strict, context, line, values)

        if 0 in self and self[0].get("NORMALIZED_TO_Y_100") == b"NO":
            # Always normalize to Y = 100
            reprstr = self.filename or (
                f"<{self.__module__}.{self.__class__.__name__} "
                f"instance at 0x{id(self):016x}>"
            )
            if self[0].normalize_to_y_100():
                print("Normalized to Y = 100:", reprstr)
            else:
                print("Warning: Could not normalize to Y = 100:", reprstr)
        self.setmodified(False)

    def _parse_data_begin_and_end(
        self, strict: bool, context: CGATS, line: bytes, values: list
    ) -> CGATS:
        """Parse data lines and handle BEGIN_ and END_ sections.

        Args:
            strict (bool): If True, raise errors for malformed data.
            context (CGATS): Current CGATS context.
            line (bytes): The line to parse.
            values (list): List of values parsed from the line.

        Returns:
            CGATS: The updated CGATS context.
        """
        if line == b"BEGIN_DATA_FORMAT":
            context["DATA_FORMAT"] = CGATS()
            context["DATA_FORMAT"].key = "DATA_FORMAT"
            context["DATA_FORMAT"].parent = context
            context["DATA_FORMAT"].root = self
            context["DATA_FORMAT"].type = b"DATA_FORMAT"
            context = context["DATA_FORMAT"]
        elif line == b"END_DATA_FORMAT":
            context = context.parent
        elif line == b"BEGIN_DATA":
            context["DATA"] = CGATS()
            context["DATA"].key = "DATA"
            context["DATA"].parent = context
            context["DATA"].root = self
            context["DATA"].type = b"DATA"
            context = context["DATA"]
        elif line == b"END_DATA":
            context = context.parent
        elif line[:6] == b"BEGIN_":
            key = line[6:].decode()
            context[key] = CGATS()
            context[key].key = key
            context[key].parent = context
            context[key].root = self
            context[key].type = b"SECTION"
            context = context[key]
        elif line[:4] == b"END_":
            context = context.parent
        elif context.type in (b"DATA_FORMAT", b"DATA"):
            if len(values):
                context = context.add_data(values)
        elif context.type == b"SECTION":
            context = context.add_data(line)
        elif len(values) > 1:
            context = self.parse_data_multi_values(strict, context, line, values)
        elif (
            values
            and values[0] not in (b"Comment:", b"Date:")
            and len(line) >= 3
            and not re.search(b"[^ 0-9A-Za-z/.]", line)
        ):
            context = self.add_data(line)
        return context

    def parse_data_multi_values(
        self, strict: bool, context: CGATS, line: bytes, values: list
    ) -> CGATS:
        """Parse multi-value data lines.

        Args:
            strict (bool): If True, raise errors for malformed data.
            context (CGATS): Current CGATS context.
            line (bytes): The line to parse.
            values (list): List of values parsed from the line.

        Returns:
            CGATS: The updated CGATS object.s
        """
        if values[0] == b"Date:":
            context.datetime = line
        elif len(values) == 2 and b'"' not in values[0]:
            key, value = values[0].decode(), values[1]
            if value is not None:
                context = context.add_data({key: value.strip(b'"')})
            else:
                context = context.add_data({key: b""})
        elif strict:
            raise CGATSInvalidError(
                "Malformed {} file: {}".format(
                    (context.parent and context.type) or "CGATS",
                    self.filename or self,
                )
            )
        return context

    def _parse_raw_data_begin(self, context: CGATS, line: bytes) -> CGATS:
        """Parse raw data line and handle BEGIN_ sections.

        Args:
            context (CGATS): The current CGATS context.
            line (bytes): The raw data line to parse.

        Returns:
            CGATS: The updated CGATS context.
        """
        if line[:6] != b"BEGIN_":
            return context
        key = line[6:].decode()
        if key in context:
            # Start new CGATS
            new = len(self)
            self[new] = CGATS()
            self[new].key = ""
            self[new].parent = self
            self[new].root = self.root
            self[new].type = b""
            context = self[new]
        return context

    def _parse_raw_data_deal_with_quotes(self, line: bytes) -> tuple[bytes, list]:
        """Parse raw data line and deal with comments and quotes.

        Args:
            line (bytes): The raw data line to parse.

        Returns:
            tuple[bytes, list]: The processed line and a list of values.
        """
        if b"#" not in line and b'"' not in line:
            # no comments or quotes
            values = line.split()
            return line, values

        # Deal with comments and quotes
        quoted = False
        values = []
        token_start = 0
        end = len(line) - 1
        for i in range(len(line)):
            char = line[i : i + 1]
            if char == b'"':
                if quoted is False:
                    if not line[token_start:i]:
                        token_start = i
                    quoted = True
                else:
                    quoted = False
            if (quoted is False and char in b"# \t") or i == end:
                if i == end:
                    i += 1
                value = line[token_start:i]
                if value:
                    if value[0:1] == b'"' == value[-2:-1]:
                        # Unquote
                        value = value[1:-1]
                        # Need to unescape double quote -> single quote
                    values.append(value.replace(b'""', b'"'))
                if char == b"#":
                    # Strip comment
                    line = line[:i].strip()
                    break
                if char in b" \t":
                    token_start = i + 1
        return line, values

    def __delattr__(self, name: str) -> None:
        """Delete attributes from CGATS dictionary.

        Args:
            name (str): The name of the attribute to delete.
        """
        del self[name]
        self.setmodified()

    def __delitem__(self, name: str) -> None:
        """Delete item from CGATS dictionary.

        Args:
            name (str): The name of the item to delete.
        """
        del self._data[name]
        self.setmodified()

    def __iter__(self):
        """Iterate over CGATS dictionary keys."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return the number of items in the CGATS dictionary."""
        return len(self._data)

    def __contains__(self, name: object) -> bool:
        """Check whether ``name`` is a stored key in the CGATS dictionary."""
        return name in self._data

    def __eq__(self, other: object) -> bool:
        """Compare raw stored data, matching the previous dict-subclass behavior.

        Deliberately compares ``_data`` directly rather than using the default
        ``Mapping.__eq__`` mixin, which would go through ``__getitem__`` (and
        thus its ``SAMPLE_ID``/``INDEX`` recomputation) instead of comparing
        literally-stored values.
        """
        if isinstance(other, CGATS):
            return self._data == other._data
        if isinstance(other, Mapping):
            return self._data == dict(other)
        return NotImplemented

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Get attributes from CGATS dictionary.

        Args:
            name (str): The name of the attribute to get.

        Raises:
            AttributeError: If the attribute is not found.

        Returns:
            Any: The value of the attribute.
        """
        if name in self:
            return self[name]
        raise AttributeError(name)

    def __getitem__(self, name: str) -> Any:  # noqa: ANN401
        """Get item from CGATS dictionary.

        Args:
            name (str): The name of the item to get.

        Raises:
            CGATSKeyError: If the item is not found.

        Returns:
            Any: The value of the item.
        """
        if name == -1:
            return self.get(len(self) - 1)
        if name in ("NUMBER_OF_FIELDS", "NUMBER_OF_SETS"):
            return getattr(self, name)
        if name in self:
            if str(name).upper() in ("INDEX", "SAMPLE_ID", "SAMPLEID"):
                if not isinstance(self.get(name), (int, float)):
                    return self.get(name)
                if str(name).upper() == "INDEX":
                    return self.key
                if isinstance(self.get(name), float):
                    return 1.0 / (self.NUMBER_OF_SETS - 1) * self.key
                return self.key + 1
            return self.get(name)
        raise CGATSKeyError(name)

    def get(self, name: int | str, default: None | Any = None) -> Any:  # noqa: ANN401
        """Get item from CGATS dictionary.

        Args:
            name (int | str): The name or index of the item to get.
            default (None | Any, optional): The value to return if the item is
                not found.

        Returns:
            Any: The value of the item or the default value if not found.
        """
        if name == -1:
            return self._data.get(len(self) - 1, default)
        if name in ("NUMBER_OF_FIELDS", "NUMBER_OF_SETS"):
            return getattr(self, name, default)
        return self._data.get(name, default)

    def get_colorants(self) -> None | list:
        """Return colorants from CGATS file.

        Returns:
            None | list: List of colorants if available, otherwise None.
        """
        color_rep = (self.queryv1("COLOR_REP") or b"").split(b"_")
        if len(color_rep) != 2:
            return None
        query = {}
        colorants = []
        for i in range(len(color_rep[0])):
            for j in range(len(color_rep[0])):
                channelname = color_rep[0][j : j + 1]
                # the key should be str
                key = b"_".join([color_rep[0], channelname]).decode("utf-8")
                query[key] = 100 if i == j else 0
            colorants.append(self.queryi1(query))
        return colorants

    def get_descriptor(self, localized: bool = True) -> bytes:
        """Return CGATS description as string, based on metadata.

        If 'localized' is True (default), include localized technology
        description for CCSS files.

        Args:
            localized (bool, optional): If True, include localized technology
                description for CCSS files. Defaults to True.

        Returns:
            bytes: CGATS description as bytes.
        """
        desc = self.queryv1("DESCRIPTOR")
        is_ccss = self.get(0, self).type == b"CCSS"
        if not desc or desc == b"Not specified" or is_ccss:
            if not is_ccss:
                desc = self.queryv1("INSTRUMENT")
                if desc:
                    display = self.queryv1("DISPLAY")
                    if display:
                        desc += b" & %s" % display
            else:
                tech = self.queryv1("TECHNOLOGY")
                if tech:
                    if (
                        desc
                        and desc != b"Not specified"
                        and desc != b"CCSS for %s" % tech
                    ):
                        display = desc
                    else:
                        display = self.queryv1("DISPLAY")
                    if localized:
                        from DisplayCAL import localization as lang

                        tech = tech.decode()
                        tech = lang.getstr(f"display.tech.{tech}", default=tech)
                        if display:
                            # Localized `tech` will always be a str,
                            # need to make sure `display` is as well.
                            display = (
                                display.decode("utf-8")
                                if isinstance(display, bytes)
                                else display
                            )
                    if display:
                        tech = f"{tech} ({display})"
                desc = tech.encode("utf-8") if isinstance(tech, str) else tech
        if not desc and self.filename:
            # With Python 3.6+ the encoding is always "utf-8" independent of the OS.
            desc = bytes(
                str(os.path.splitext(os.path.basename(self.filename))[0]), "utf-8"
            )
        return desc

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set attributes on the CGATS object.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        if name in ("_keys", "_lvl", "_data"):
            object.__setattr__(self, name, value)
        elif name == "modified":
            self.setmodified(value)
        elif name in (
            "datetime",
            "filename",
            "fileName",
            "file_identifier",
            "key",
            "mtime",
            "normalize_fields",
            "parent",
            "root",
            "type",
            "vmaxlen",
            "emit_keywords",
        ):
            object.__setattr__(self, name, value)
            self.setmodified()
        else:
            self[name] = value

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set item in CGATS dictionary.

        Args:
            name (str): The name of the item to set.
            value (Any): The value to set for the item.
        """
        self._data[name] = value
        self.setmodified()

    def setmodified(self, modified: bool = True) -> None:
        """Set 'modified' state on the 'root' object."""
        if self.root and self.root._modified != modified:
            object.__setattr__(self.root, "_modified", modified)

    def __bytes__(self) -> bytes:
        """Return CGATS data as bytes.

        Returns:
            bytes: CGATS data as bytes.
        """
        result = []
        lvl = self.root._lvl
        self.root._lvl += 1
        data = None
        if self.type == b"SAMPLE":
            result.append(
                b" ".join(
                    rpad(self[item], self.parent.vmaxlen + (1 if self[item] < 0 else 0))
                    for item in list(self.parent.parent["DATA_FORMAT"].values())
                )
            )
        elif self.type == b"DATA":
            data = self
        elif self.type == b"DATA_FORMAT":
            result.append(b" ".join(list(self.values())))
        else:
            data, result = self.__bytes_from_subsections(data, result)
        if data and data.parent["DATA_FORMAT"]:
            if "KEYWORDS" in data.parent and self.emit_keywords:
                result.extend(
                    b'KEYWORD "%s"' % item
                    for item in list(data.parent["DATA_FORMAT"].values())
                    if item in list(data.parent["KEYWORDS"].values())
                )
            result.append(
                b"NUMBER_OF_FIELDS %s"
                % bytes(str(len(data.parent["DATA_FORMAT"])), "utf-8")
            )
            result.append(b"BEGIN_DATA_FORMAT")
            result.append(b" ".join(list(data.parent["DATA_FORMAT"].values())))
            result.append(b"END_DATA_FORMAT")
            result.append(b"")
            result.append(b"NUMBER_OF_SETS %s" % (bytes(str(len(data)), "utf-8")))
            result.append(b"BEGIN_DATA")
            result.extend(
                b" ".join(
                    [
                        rpad(
                            data[key][item.decode("utf-8")],
                            data.vmaxlen
                            + (1 if data[key][item.decode("utf-8")] < 0 else 0),
                        )
                        for item in list(data.parent["DATA_FORMAT"].values())
                    ]
                )
                for key in data
            )
            result.append(b"END_DATA")
        if (
            ((self.parent and self.parent.type) or self.type) == b"ROOT"
            and result
            and result[-1] != b""
            and lvl == 0
        ):
            # Add empty line at end if not yet present
            result.append(b"")
        self.root._lvl -= 1
        return b"\n".join(result)

    def __bytes_from_subsections(self, data: CGATS, result: list) -> tuple[CGATS, list]:
        """Generate bytes from subsections.

        Args:
            data (CGATS): The CGATS data to process.
            result (list): The list to append the generated bytes to.

        Returns:
            tuple[CGATS, list]: A tuple containing the data and the result
                list.
        """
        if self.datetime:
            result.append(self.datetime)
        if self.type == b"SECTION":
            result.append(b"BEGIN_" + self.key.encode())
        elif self.parent and self.parent.type == b"ROOT":
            # Make sure CGATS file identifiers are always a minimum of 7 characters
            result.append(self.type.ljust(7))
            result.append(b"")

        data, result = self.__bytes_from_subsection_data(data, result)

        if self.type == b"SECTION":
            result.append(b"END_" + self.key.encode())
        if self.type == b"SECTION" or data:
            result.append(b"")
        return data, result

    def __bytes_from_subsection_data(
        self, data: CGATS, result: list
    ) -> tuple[CGATS, list]:
        """Generate bytes from subsection data.

        Args:
            data (CGATS): The CGATS data to process.
            result (list): The list to append the generated bytes to.

        Returns:
            tuple[CGATS, list]: A tuple containing the data and the result
                list.
        """
        if self.type in (b"DATA", b"DATA_FORMAT", b"KEYWORDS", b"SECTION"):
            iterable = self
        else:
            iterable = self.keys()
        for key in iterable:
            value = self[key]
            value = value.encode("utf-8") if isinstance(value, str) else value

            if key == "DATA":
                data = value
            elif isinstance(value, (float, int, bytes)):
                if key not in ("NUMBER_OF_FIELDS", "NUMBER_OF_SETS"):
                    if isinstance(key, int):
                        result.append(
                            value
                            if isinstance(value, bytes)
                            else bytes(str(value), "utf-8")
                        )
                    else:
                        if (
                            "KEYWORDS" in self
                            and key in list(self["KEYWORDS"].values())
                            and self.emit_keywords
                        ):
                            result.append(b'KEYWORD "%s"' % key.encode())
                        if isinstance(value, bytes):
                            # Need to escape single quote -> double quote
                            value = value.replace(b'"', b'""')
                        if isinstance(value, (float, int)):
                            value = bytes(str(value), "utf-8")
                        result.append(b'%s "%s"' % (key.encode(), value))
            elif key not in ("DATA_FORMAT", "KEYWORDS"):
                if value.type == b"SECTION" and result[-1:] and result[-1:][0] != b"":
                    result.append(b"")
                result.append(bytes(value))
        return data, result

    def add_keyword(self, keyword: str, value: None | str = None) -> None:
        """Add a keyword to the list of keyword values.

        Args:
            keyword (str): The keyword to add.
            value (str, optional): The value associated with the keyword.
                Defaults to None.
        """
        if isinstance(keyword, bytes):
            keyword = keyword.decode()

        if self.type in (b"DATA", b"DATA_FORMAT", b"KEYWORDS", b"SECTION"):
            context = self.parent
        elif self.type == b"SAMPLE":
            context = self.parent.parent
        else:
            context = self
        if "KEYWORDS" not in context:
            context["KEYWORDS"] = CGATS()
            context["KEYWORDS"].key = "KEYWORDS"
            context["KEYWORDS"].parent = context
            context["KEYWORDS"].root = self.root
            context["KEYWORDS"].type = b"KEYWORDS"
        if keyword.encode() not in list(context["KEYWORDS"].values()):
            newkey = len(context["KEYWORDS"])
            while newkey in context["KEYWORDS"]:
                newkey += 1
            context["KEYWORDS"][newkey] = keyword.encode()
        if value is not None:
            context[keyword] = value

    def add_section(self, key: str, value: str) -> None:
        """Add a section to the CGATS data.

        Args:
            key (str): The key for the section.
            value (str): The value for the section.
        """
        self[key] = CGATS()
        self[key].key = key
        self[key].parent = self
        self[key].root = self
        self[key].type = b"SECTION"
        self[key].add_data(value)

    def remove_keyword(self, keyword: str, remove_value: bool = True) -> None:
        """Remove a keyword from the list of keyword values.

        Args:
            keyword (str): The keyword to remove.
            remove_value (bool): If True, also remove the value associated
                with the keyword. Defaults to True.
        """
        if self.type in (b"DATA", b"DATA_FORMAT", b"KEYWORDS", b"SECTION"):
            context = self.parent
        elif self.type == b"SAMPLE":
            context = self.parent.parent
        else:
            context = self
        for key in list(context["KEYWORDS"].keys()):
            if context["KEYWORDS"][key] == keyword.encode():
                del context["KEYWORDS"][key]
        if remove_value:
            del context[keyword]

    def insert(self, key: None | int = None, data: None | CGATS = None) -> None:
        """Insert data at index key. Also see add_data method.

        Args:
            key (int, optional): The index at which to insert the data.
                If None, data is appended. Defaults to None.
            data (CGATS, optional): The CGATS data to insert. If None,
                the current CGATS instance is used. Defaults to None.
        """
        self.add_data(data, key)

    def append(self, data: CGATS) -> None:
        """Append data. Also see add_data method.

        Args:
            data (CGATS): The CGATS data to append.
        """
        self.add_data(data)

    def get_data(self, field_names: None | tuple = None) -> bool | CGATS:
        """Get CGATS data.

        Args:
            field_names (tuple, optional): A tuple of field names to query.
                If None, all data is returned. Defaults to None.

        Returns:
            bool | CGATS: A dictionary containing the CGATS data.
        """
        data = self.queryv1("DATA")
        if not data:
            return False
        if field_names:
            data = data.queryi(field_names)
        return data

    def get_rgb_xyz_values(self) -> tuple[bool, bool] | tuple[CGATS, list]:
        """Get RGB and XYZ values from the CGATS data.

        Returns:
            tuple: A tuple containing two elements:
                - A dictionary with RGB and XYZ values.
                - A list of lists containing RGB and XYZ values in the order:
                  [R, G, B, X, Y, Z].
            If no data is found, returns (False, False).
        """
        field_names = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
        data = self.get_data(field_names)
        if not data:
            return False, False
        values_list = [
            [data[_key][field_name] for field_name in field_names] for _key in data
        ]
        return data, values_list

    def set_rgb_xyz_values(self, values_list: list) -> bool:
        """Set RGB and XYZ values in the CGATS data.

        Args:
            values_list (list): A list of RGB and XYZ values, where each entry
                is a list containing RGB and XYZ values in the order:
                [R, G, B, X, Y, Z].

        Returns:
            bool: True if values were set successfully, False otherwise.
        """
        field_names = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
        for i, values in enumerate(values_list):
            for j, field_name in enumerate(field_names):
                self[i][field_name] = values[j]
        return True

    def checkerboard(
        self,
        sort1: Callable = sort_by_l,
        sort2: Callable = sort_rgb_white_to_top,
        split_grays: bool = False,
        shift: bool = False,
    ) -> bool:
        """Return a checkerboard of RGB values.

        Args:
            sort1 (Callable): Function to sort the first dimension.
            sort2 (Callable): Function to sort the second dimension.
            split_grays (bool): If True, split grays from colors.
            shift (bool): If True, shift values in checkerboard.

        Returns:
            bool: True if checkerboard was created successfully, False
                otherwise.
        """
        data, values_list = self.get_rgb_xyz_values()
        if not values_list:
            return False
        numvalues = len(values_list)
        values_list = (
            sorted(values_list, key=functools.cmp_to_key(sort1))
            if sort1
            else values_list
        )
        values_list = (
            sorted(values_list, key=functools.cmp_to_key(sort2))
            if sort2
            else values_list
        )
        gray = []
        color = (
            self.split_grays(values_list, gray, numvalues)
            if split_grays
            else values_list
        )
        checkerboard = []
        for values_list in [gray, color]:
            if not values_list:
                continue
            split = round(len(values_list) / 2.0)
            values_list1 = values_list[:split]
            values_list2 = values_list[split:]
            if shift:
                # Shift values.
                #
                # If split is even:
                #   A1 A2 A3 A4 -> A1 B2 B3 B1 B4
                #   B1 B2 B3 B4 -> A3 A4 A2
                #
                # If split is uneven:
                #   A1 A2 A3 -> A1 B1 B2 B3 B4
                #   B1 B2 B3 B4 -> A2 A3
                offset = 0
                if split == len(values_list) / 2.0:
                    # Even split
                    offset += 1
                values_list1_orig = list(values_list1)
                values_list2_orig = list(values_list2)
                values_list1 = values_list2_orig[offset:]
                values_list2 = values_list1_orig[offset + 1 :]
                values_list1.insert(0, values_list1_orig[0])
                if offset:
                    values_list1.insert(-1, values_list2_orig[0])
                    values_list2.extend(values_list1_orig[1:2])
            # Interleave.
            # 1 2 3 4 5 6 7 8 -> 1 5 2 6 3 7 4 8
            while values_list1 or values_list2:
                for values_list in (values_list1, values_list2):
                    if values_list:
                        values = values_list.pop(0)
                        checkerboard.append(values)
        if shift and checkerboard[-1][:3] == [100, 100, 100]:
            # Move white patch to front
            debug_print("INFO - moving white to front")
            checkerboard.insert(0, checkerboard.pop())
        if len(checkerboard) != numvalues:
            # This should never happen
            print(
                "Number of patches incorrect after re-ordering "
                f"(is {len(checkerboard)}, should be {numvalues})"
            )
            return False
        return data.set_rgb_xyz_values(checkerboard)

    def split_grays(self, values_list: list, gray: list, numvalues: int) -> list:
        """Split values into gray and color.

        Args:
            values_list (list): List of RGB values.
            gray (list): List to store gray values.
            numvalues (int): Total number of values.

        Returns:
            list: List of color and gray values.
        """
        # Split values into gray and color. First gray in a consecutive
        # sequence of two or more grays will be added to color list,
        # following grays will be added to gray list.
        color = []
        prev_i = -1
        prev_values = []
        added = {prev_i: True}  # Keep track of entries we have added
        for i, values in enumerate(values_list):
            debug_print(i + 1, "IN", values[:3])
            is_gray = values[:3] == [values[:3][0]] * 3
            prev = color
            cur = color
            if is_gray:
                if not prev_values:
                    debug_print("WARNING - skipping gray because no prev")
                elif values[:3] == prev_values[:3]:
                    # Same gray as prev value
                    prev = color
                    cur = gray
                    debug_print(
                        f"INFO - appending prev {prev_values[:3]} to color "
                        "because prev was same gray but got skipped",
                        other_conditions=prev_i not in added,
                    )
                    debug_print(
                        "INFO - appending cur to gray because prev "
                        f"{prev_values[:3]} was same gray"
                    )
                elif prev_values[:3] == [prev_values[:3][0]] * 3:
                    # Prev value was different gray
                    prev = gray
                    cur = gray
                    debug_print(
                        f"INFO - appending prev {prev_values[:3]} to gray "
                        "because prev was different gray but got skipped",
                        other_conditions=prev_i not in added,
                    )
                    debug_print(
                        "INFO - appending cur to gray because prev "
                        f"{prev_values[:3]} was different gray"
                    )
                elif i < numvalues - 1:
                    debug_print(
                        "WARNING - skipping gray because prev "
                        f"{prev_values[:3]} was not gray"
                    )
                else:
                    # Last
                    debug_print(
                        "INFO - appending cur to color because prev "
                        f"{prev_values[:3]} was not gray but cur is last"
                    )
            if not is_gray or cur is gray or i == numvalues - 1:
                if prev_i not in added:
                    debug_print(
                        f"INFO - appending prev {prev_values[:3]} "
                        "to color because prev got skipped",
                        other_conditions=prev is cur is color,
                    )
                    prev.append(prev_values)
                    added[prev_i] = True
                debug_print(
                    "INFO - appending cur to color",
                    other_conditions=not is_gray and cur is color,
                )
                cur.append(values)
                added[i] = True
            prev_i = i
            prev_values = values
        return color

    def sort_rgb_gray_to_top(self) -> bool:
        """Sort RGB values with gray at the top.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_rgb_gray_to_top)

    def sort_rgb_to_top(
        self, red: bool = False, green: bool = False, blue: bool = False
    ) -> bool:
        """Sort quantities of R, G or B (or combinations) to top.

        Example: sort_RGB_to_top(True, False, False) - sort red values to top
        Example: sort_RGB_to_top(False, True, True) - sort cyan values to top

        Args:
            red (bool): If True, sort red values to top.
            green (bool): If True, sort green values to top.
            blue (bool): If True, sort blue values to top.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        if red and green and blue:
            function = sort_rgb_gray_to_top
        elif red and green:
            function = sort_rgb_to_top_factory(0, 1, 2, 0)
        elif red and blue:
            function = sort_rgb_to_top_factory(0, 2, 1, 0)
        elif green and blue:
            function = sort_rgb_to_top_factory(1, 2, 0, 1)
        elif red:
            function = sort_rgb_to_top_factory(1, 2, 1, 0)
        elif green:
            function = sort_rgb_to_top_factory(0, 2, 0, 1)
        elif blue:
            function = sort_rgb_to_top_factory(0, 1, 0, 2)
        else:
            return False
        return self.sort_data_rgb_xyz(function)

    def sort_rgb_white_to_top(self) -> bool:
        """Sort RGB values with white at the top.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_rgb_white_to_top)

    def sort_by_hsi(self) -> bool:
        """Sort by HSI values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_hsi)

    def sort_by_hsl(self) -> bool:
        """Sort by HSL values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_hsl)

    def sort_by_hsv(self) -> bool:
        """Sort by HSV values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_hsv)

    def sort_by_l(self) -> bool:
        """Sort by L values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_l)

    def sort_by_rgb(self) -> bool:
        """Sort by RGB values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_rgb)

    def sort_by_bgr(self) -> bool:
        """Sort by BGR values.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_bgr)

    def sort_by_rgb_pow_sum(self) -> bool:
        """Sort by RGB power sum.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_rgb_pow_sum)

    def sort_by_rgb_sum(self) -> bool:
        """Sort by RGB sum.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_rgb_sum)

    def sort_by_rec709_luma(self) -> bool:
        """Sort by Rec. 709 luma.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        return self.sort_data_rgb_xyz(sort_by_rec709_luma)

    def sort_data_rgb_xyz(
        self,
        cmp: None | Callable = None,
        key: None | Callable = None,
        reverse: bool = False,
    ) -> bool:
        """Sort RGB/XYZ data.

        Args:
            cmp (callable, optional): Comparison function to use for sorting.
            key (callable, optional): Key function to use for sorting.
            reverse (bool, optional): If True, sort in descending order.

        Returns:
            bool: True if sorting was successful, False otherwise.
        """
        data, valueslist = self.get_rgb_xyz_values()
        if not valueslist:
            return False
        valueslist = sorted(valueslist, key=functools.cmp_to_key(cmp), reverse=reverse)
        return data.set_rgb_xyz_values(valueslist)

    @property
    def modified(self) -> bool:
        """Return whether the CGATS object has been modified.

        Returns:
            bool: True if modified, False otherwise.
        """
        if self.root:
            return self.root._modified
        return self._modified

    def moveby1(self, start: int, inc: int = 1) -> None:
        """Move items from start by incrementing or decrementing their key by inc.

        Args:
            start (int): The starting index from which to move items.
            inc (int, optional): The increment by which to move items.
                Defaults to 1.
        """
        r = range(start, len(self) + 1)
        if inc > 0:
            r = reversed(r)
        for key in r:
            if key in self:
                if key + inc < 0:
                    break
                self[key].key += inc
                self[key + inc] = self[key]
                if key == len(self) - 1:
                    break

    def add_data(
        self, data: bytes | str | dict | list | tuple | CGATS, key: None | int = None
    ) -> CGATS:
        """Add data to the CGATS structure.

        Args:
            data (bytes | str | dict | list | tuple | CGATS): The data to add.
            key (None | int, optional): The index at which to insert the data.
                If None, data is appended. Defaults to None.

        Returns:
            CGATS: The context in which the data was added.
        """
        context = self
        if self.type == b"DATA":
            key = self._add_data_array_type(data, key)
        elif self.type == b"ROOT":
            key, context = self._add_data_root(data, key)
        elif self.type == b"SECTION":
            self._add_data_section(data, key)
        elif self.type in (b"DATA_FORMAT", b"KEYWORDS") or (
            self.parent and self.parent.type == b"ROOT"
        ):
            self._add_data_format_or_keywords(data)
        else:
            raise CGATSInvalidOperationError(f"Cannot add data to {self.type}")
        return context

    def _add_data_format_or_keywords(self, data: dict | list | tuple) -> None:
        """Add data to DATA_FORMAT or KEYWORDS type.

        Args:
            data (dict | list | tuple): The data to add.

        Raises:
            CGATSTypeError: If the data type is invalid.
        """
        if not isinstance(data, (Mapping, list, tuple)):
            raise CGATSTypeError(
                f"Invalid data type for {self.type} (expected "
                f"CGATS, dict, list or tuple, got {type(data)})"
            )

        for var in data:
            var = var.decode() if isinstance(var, bytes) else var

            if var in ("NUMBER_OF_FIELDS", "NUMBER_OF_SETS"):
                self[var] = None
                continue

            if isinstance(data, Mapping):
                if self.type in (b"DATA_FORMAT", b"KEYWORDS"):
                    key, value = len(self), data[var]
                else:
                    key, value = var, data[var]
            else:
                key, value = len(self), var.encode()

            if (
                self.root.normalize_fields
                and (self.type in (b"DATA_FORMAT", b"KEYWORDS") or var == "KEYWORD")
                and isinstance(value, bytes)
            ):
                value = value.upper()
                value = value.replace(b"SAMPLEID", b"SAMPLE_ID").replace(
                    b"SAMPLENAME", b"SAMPLE_NAME"
                )
                # if value == b"SAMPLEID":
                #     value = b"SAMPLE_ID"
                # elif value == b"SAMPLENAME":
                #     value = b"SAMPLE_NAME"

            if var == "KEYWORD":
                self.emit_keywords = True
                if value != b"KEYWORD":
                    self.add_keyword(value)
                else:
                    print('Warning: cannot add keyword "KEYWORD"')
            else:
                value = self.__add_data_from_bytes_value(key, value)
                self[key] = value

    def __add_data_from_bytes_value(
        self, key: int | str, value: bytes | str
    ) -> int | float:
        """Add data from bytes value.

        Args:
            key (int | str): The key for the data.
            value (bytes | str): The value to add.

        Raises:
            CGATSTypeError: If the value type is invalid.

        Returns:
            int | float: The value converted to int or float if applicable.
        """
        if isinstance(value, bytes) and key not in (
            "DESCRIPTOR",
            "ORIGINATOR",
            "CREATED",
            "DEVICE_CLASS",
            "COLOR_REP",
            "TARGET_INSTRUMENT",
            "LUMINANCE_XYZ_CDM2",
            "OBSERVER",
            "INSTRUMENT",
            "MANUFACTURER_ID",
            "MANUFACTURER",
            "REFERENCE",
            "REFERENCE_OBSERVER",
            "DISPLAY",
            "TECHNOLOGY",
            "REFERENCE_FILENAME",
            "REFERENCE_HASH",
            "TARGET_FILENAME",
            "TARGET_HASH",
            "FIT_METHOD",
        ):
            match = re.match(rb"(?:\d+|((?:\d*\.\d+|\d+)(?:e[+-]?\d+)?))$", value)
            if match:
                value = float(value) if match.groups()[0] else int(value)
                if self.type in (b"DATA_FORMAT", b"KEYWORDS"):
                    raise CGATSTypeError(
                        f"Invalid data type for {self.type} "
                        "(expected bytes or str, "
                        f"got {type(value)})"
                    )
        return value

    def _add_data_section(self, data: str | CGATS, key: None | int = None) -> None:
        """Add data to SECTION type.

        Args:
            data (str | CGATS): The data to add.
            key (None | int, optional): The index at which to insert the data.
                If None, data is appended. Defaults to None.

        Raises:
            CGATSTypeError: If the data type is invalid.
        """
        if isinstance(data, bytes):
            if isinstance(key, int):
                # accept only integer keys.
                # move existing items
                self.moveby1(key)
            else:
                key = len(self)
            self[key] = data
        else:
            raise CGATSTypeError(
                f"Invalid data type for {self.type} "
                f"(expected bytes or str, got {type(data)})"
            )

    def _add_data_root(
        self, data: bytes | str, key: None | int = None
    ) -> tuple[int, CGATS]:
        """Add data to ROOT type.

        Args:
            data (bytes | str): The data to add.
            key (None | int, optional): The index at which to insert the data.
                If None, data is appended. Defaults to None.

        Returns:
            tuple[int, CGATS]: A tuple containing the key at which the data was added
                and the CGATS context where the data was added.
        """
        if isinstance(data, bytes) and data.find(b"\n") < 0 and data.find(b"\r") < 0:
            if isinstance(key, int):
                # accept only integer keys.
                # move existing items
                self.moveby1(key)
            else:
                key = len(self)
            self[key] = CGATS()
            self[key].key = key
            self[key].parent = self
            self[key].root = self.root
            self[key].type = data
            context = self[key]
        elif not len(self):
            context = self.add_data(self.file_identifier)  # create root element
            context = context.add_data(data, key)
        else:
            raise CGATSTypeError(
                f"Invalid data type for {self.type} "
                f"(expected str or unicode without line endings, got {type(data)})"
            )

        return key, context

    def _add_data_array_type(
        self, data: dict | list | tuple | CGATS, key: None | int = None
    ) -> int:
        """Add data to DATA type.

        Args:
            data (CGATS | dict | list | tuple): The data to add.
            key (None | int, optional): The index at which to insert the data.
                If None, data is appended. Defaults to None.

        Raises:
            CGATSTypeError: If the data type is invalid.
            CGATSInvalidOperationError: If DATA_FORMAT is missing.

        Returns:
            int: The key at which the data was added.
        """
        if not isinstance(data, (Mapping, list, tuple)):
            raise CGATSTypeError(
                f"Invalid data type for {self.type} (expected CGATS, dict, list or "
                f"tuple, got {type(data)})"
            )

        if not self.parent["DATA_FORMAT"]:
            raise CGATSInvalidOperationError(
                "Cannot add to DATA because of missing DATA_FORMAT"
            )

        fl, il = len(self.parent["DATA_FORMAT"]), len(data)
        if fl != il:
            raise CGATSTypeError(f"DATA entries take exactly {fl} values ({il} given)")
        dataset = CGATS()
        dataset = self._add_data_from_data_format_values(data, dataset)
        if isinstance(key, int):
            # accept only integer keys.
            # move existing items
            self.moveby1(key)
        else:
            key = len(self)
        dataset.key = key
        dataset.parent = self
        dataset.root = self.root
        dataset.type = b"SAMPLE"
        self[key] = dataset

        return key

    def _add_data_from_data_format_values(
        self, data: dict | list | tuple, dataset: CGATS
    ) -> CGATS:
        """Add data from DATA_FORMAT values.

        Args:
            data (dict | list | tuple): The data to add.
            dataset (CGATS): The CGATS instance to which the data will be added.

        Returns:
            CGATS: The updated CGATS instance with the added data.
        """
        for i, item in enumerate(list(self.parent["DATA_FORMAT"].values())):
            if isinstance(data, Mapping):
                try:
                    value = data[item.decode()]
                except KeyError as e:
                    raise CGATSKeyError(item) from e
            else:
                value = data[i]
            if item.upper() in (b"INDEX", b"SAMPLE_ID", b"SAMPLEID"):
                item, value = self._add_data_from_sample_id(item, value)
            elif item.upper() not in (b"SAMPLE_NAME", b"SAMPLE_LOC", b"SAMPLENAME"):
                value = self._add_data_from_sample_name(item, value)
            elif self.root.normalize_fields and item.upper() == b"SAMPLENAME":
                item = b"SAMPLE_NAME"
            dataset[item.decode()] = value
        return dataset

    def _add_data_from_sample_id(
        self, item: bytes, value: bytes | str | float
    ) -> tuple[bytes, int | float]:
        """Add data from sample ID.

        Args:
            item (bytes): The item key.
            value (bytes | str | float): The value associated with the
                item.

        Returns:
            tuple[bytes, int | float]: The processed item key and value.
        """
        if self.root.normalize_fields and item.upper() == b"SAMPLEID":
            item = b"SAMPLE_ID"
            # allow alphanumeric INDEX / SAMPLE_ID
        if isinstance(value, bytes):
            match = re.match(rb"(?:\d+|((?:\d*\.\d+|\d+)(?:e[+-]?\d+)?))$", value)
            if match:
                value = float(value) if match.groups()[0] else int(value)
        return item, value

    def _add_data_from_sample_name(
        self, item: bytes, value: bytes | str | float
    ) -> float:
        """Add data from sample name.

        Args:
            item (bytes): The item key.
            value (bytes | str | float): The value associated with the
                item.

        Returns:
            float: The processed value.
        """
        try:
            value = parse_float(value)
        except ValueError as e:
            raise CGATSValueError(
                f"Invalid data type for {item} "
                f"(expected float, got {value.__class__.__name__})"
            ) from e
        else:
            strval = bytes(str(abs(value)), "UTF-8")
            if (
                self.parent.type != b"CAL" and item.startswith(b"RGB_")
            ) or item.startswith(b"CMYK_"):
                # Assuming 0..100, 4 decimal digits is
                # enough for roughly 19 bits integer
                # device values
                parts = strval.split(b".")
                if len(parts) == 2 and len(parts[-1]) > 4:
                    value = round(value, 4)
                    strval = bytes(str(abs(value)), "UTF-8")
            parts = strval.split(b"e")
            lencheck = len(parts[0])
            if len(parts) > 1:
                lencheck += abs(int(parts[1]))
            self.vmaxlen = max(self.vmaxlen, lencheck)
        return value

    def export_3d(
        self,
        filename: str,
        colorspace: str = "RGB",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
        compress: bool = True,
        file_format: str = "VRML",
    ) -> None:
        """Export 3D data to a file in the specified colorspace.

        Args:
            filename (str): The name of the file to export to.
            colorspace (str): The colorspace to use for the export.
                Supported values are: "DIN99", "DIN99b", "DIN99c", "DIN99d",
                "LCH(ab)", "LCH(uv)", "Lab", "Luv", "Lu'v'", "RGB", "xyY",
                "HSI", "HSL", "HSV", "ICtCp", "IPT", and "Lpt".
            rgb_black_offset (float): The offset for black in RGB space.
            normalize_rgb_white (bool): Whether to normalize RGB white.
            compress (bool): Whether to compress the output file.
            file_format (str): The format of the output file, e.g., 'VRML'.

        Raises:
            ValueError: If the specified colorspace is not supported.
        """
        if colorspace not in ColorSpaceToVRML.VALID_COLOR_SPACE_NAMES:
            raise ValueError(f"export_3d: Unknown colorspace {colorspace!r}")

        if self.queryv1("ACCURATE_EXPECTED_VALUES") == "true":
            cat = "Bradford"
        else:
            cat = "XYZ scaling"
        data = self.queryv1("DATA")

        white = data.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
        white = white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"] if white else "D50"
        white = colormath.get_whitepoint(white)

        colorspace_to_vrml: ColorSpaceToVRML = COLORSPACE_NAME_TO_VRML_MAP[colorspace](
            data=data,
            white_point=white,
            cat=cat,
            rgb_black_offset=rgb_black_offset,
            normalize_rgb_white=normalize_rgb_white,
        )
        colorspace_to_vrml.generate_vrml()
        colorspace_to_vrml.write_vrml(
            file_format=file_format,
            filename=filename,
            compress=compress,
        )

    @property
    def NUMBER_OF_FIELDS(self) -> int:  # noqa: N802
        """Get number of fields.

        Returns:
            int: Number of fields in the CGATS object.
        """
        if "DATA_FORMAT" in self:
            return len(self["DATA_FORMAT"])
        return 0

    @property
    def NUMBER_OF_SETS(self) -> int:  # noqa: N802
        """Get number of sets.

        Returns:
            int: Number of sets in the CGATS object.
        """
        if "DATA" in self:
            return len(self["DATA"])
        return 0

    def query(  # noqa: C901
        self,
        query: str | dict | list | tuple,
        query_value: None | Any = None,  # noqa: ANN401
        get_value: bool = False,
        get_first: bool = False,
    ) -> int | float | bytes | CGATS:
        """Return CGATS object of items or values where query matches.

        Query can be a dict with key / value pairs, a tuple or a string.
        Return empty CGATS object if no matching items found.

        Args:
            query (str | dict | list | tuple): The query to match against.
            query_value (Any, optional): The value to match against the query.
            get_value (bool): If True, return values instead of items.
            get_first (bool): If True, return only the first matching item or
                value.

        Returns:
            int | float | bytes | CGATS: Matching items or values.
        """
        # TODO: Simplify this method.
        modified = self.modified
        result = CGATS() if not get_first else None
        if not isinstance(query, (Mapping, list, tuple)):
            query = (query,)

        items = [self] + [self[key] for key in self]
        for item in items:
            if not isinstance(item, (Mapping, list, tuple)):
                continue
            if not get_first:
                n = len(result)
            result_n = CGATS() if get_value else None
            match_count = 0
            for query_key in query:
                if query_key in item or (
                    isinstance(item, CGATS)
                    and (
                        (query_key == "NUMBER_OF_FIELDS" and "DATA_FORMAT" in item)
                        or (query_key == "NUMBER_OF_SETS" and "DATA" in item)
                    )
                ):
                    current_query_value = (
                        query[query_key]
                        if query_value is None and isinstance(query, Mapping)
                        else query_value
                    )
                    if (
                        current_query_value is not None
                        and item[query_key] != current_query_value
                    ):
                        break
                    if get_value:
                        result_n[len(result_n)] = item[query_key]
                    match_count += 1
                else:
                    break

            if match_count == len(query):
                if not get_value:
                    result_n = item
                if result_n is not None:
                    if get_first:
                        result = (
                            result_n[0]
                            if (
                                get_value
                                and isinstance(result_n, Mapping)
                                and len(result_n) == 1
                            )
                            else result_n
                        )
                        break
                    if len(result_n):
                        result[n] = (
                            result_n[0]
                            if (
                                get_value
                                and isinstance(result_n, Mapping)
                                and len(result_n) == 1
                            )
                            else result_n
                        )

            if isinstance(item, CGATS) and item != self:
                result_n = item.query(query, query_value, get_value, get_first)
                if result_n is not None:
                    if get_first:
                        result = result_n
                        break
                    if len(result_n):
                        for i in result_n:
                            n = len(result)
                            if result_n[i] not in list(result.values()):
                                result[n] = result_n[i]

        if isinstance(result, CGATS):
            result.setmodified(modified)
        return result

    def queryi(
        self,
        query: str | dict | list | tuple,
        query_value: None | Any = None,  # noqa: ANN401
    ) -> int | float | bytes | CGATS:
        """Query and return matching items. See also query method.

        Args:
            query (str | dict | list | tuple): The query to match against.
            query_value (Any, optional): The value to match against the query.

        Returns:
            int | float | bytes | CGATS: The matching items or CGATS object.
        """
        return self.query(query, query_value, get_value=False, get_first=False)

    def queryi1(
        self,
        query: str | dict | list | tuple,
        query_value: None | Any = None,  # noqa: ANN401
    ) -> int | float | bytes | CGATS:
        """Query and return first matching item. See also query method.

        Args:
            query (str | dict | list | tuple): The query to match against.
            query_value (Any, optional): The value to match against the query.

        Returns:
            int | float | bytes | CGATS: The first matching item or CGATS object.
        """
        return self.query(query, query_value, get_value=False, get_first=True)

    def queryv(
        self,
        query: str | dict | list | tuple,
        query_value: None | Any = None,  # noqa: ANN401
    ) -> int | float | bytes | CGATS:
        """Query and return matching values. See also query method.

        Args:
            query (str | dict | list | tuple): The query to match against.
            query_value (Any, optional): The value to match against the query.

        Returns:
            int | float | bytes | CGATS: The matching values or CGATS object.
        """
        return self.query(query, query_value, get_value=True, get_first=False)

    def queryv1(
        self,
        query: str | dict | list | tuple,
        query_value: None | Any = None,  # noqa: ANN401
    ) -> int | float | bytes | CGATS:
        """Query and return first matching value. See also query method.

        Args:
            query (str | dict | list | tuple): The query to match against.
            query_value (Any, optional): The value to match against the query.

        Returns:
            int | float | bytes | CGATS: The first matching value or CGATS object.
        """
        return self.query(query, query_value, get_value=True, get_first=True)

    def remove(self, item: int | str | CGATS) -> Any:  # noqa: ANN401
        """Remove an item from the internal CGATS structure."""
        key = item.key if isinstance(item, CGATS) else item
        maxindex = len(self) - 1
        result = self[key]
        if isinstance(key, int) and key != maxindex:
            self.moveby1(key + 1, -1)
        name = len(self) - 1
        self._data.pop(name, None)
        self.setmodified()
        return result

    def convert_xyz_to_lab(self) -> None:
        """Convert XYZ to D50 L*a*b* and add it as additional fields.

        Raises:
            NotImplementedError: If the color representation is not supported.
            CGATSError: If no data or white patch is found.
        """
        color_rep = (self.queryv1("COLOR_REP") or b"").split(b"_")

        if color_rep[1] == b"LAB":
            # Nothing to do
            return

        if (
            len(color_rep) != 2
            or color_rep[0] not in (b"RGB", b"CMYK")
            or color_rep[1] != b"XYZ"
        ):
            raise NotImplementedError(
                "Got unsupported color representation {}".format(
                    b"_".join(color_rep).decode("utf-8")
                )
            )

        data = self.queryv1("DATA")
        if not data:
            raise CGATSError("No data")

        white = self._get_white_patch(color_rep, data)
        if not white:
            raise CGATSError("Missing white patch")

        device_labels = []
        for i in range(len(color_rep[0])):
            channel = color_rep[0][i : i + 1]
            device_labels.append(color_rep[0] + b"_" + channel)

        # Always XYZ
        cie_labels = []
        for i in range(len(color_rep[1])):
            channel = color_rep[1][i : i + 1]
            cie_labels.append(color_rep[1] + b"_" + channel)

        # Add entries to DATA_FORMAT
        lab_data_format = (b"LAB_L", b"LAB_A", b"LAB_B")
        for label in lab_data_format:
            if label not in list(data.parent.DATA_FORMAT.values()):
                data.parent.DATA_FORMAT.add_data((label,))

        # Add L*a*b* to each sample
        for _key in data:
            sample = data[_key]
            cie_values = [sample[label.decode("utf-8")] for label in cie_labels]
            lab = colormath.XYZ2Lab(*cie_values)
            for i, label in enumerate(lab_data_format):
                sample[label] = lab[i]

    def _get_white_patch(self, color_rep: tuple, data: CGATS) -> None | bytes:
        """Get the white patch based on the color representation.

        Args:
            color_rep (tuple): The color representation of the sample.
            data (CGATS): The CGATS data object containing samples.

        Returns:
            None | bytes: The white patch values for the color representation,
                or None if not found.
        """
        white = None
        if color_rep[0] == b"RGB":
            white = data.queryv1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
        elif color_rep[0] == b"CMYK":
            white = data.queryv1({"CMYK_C": 0, "CMYK_M": 0, "CMYK_Y": 0, "CMYK_K": 0})
        return white

    def fix_zero_measurements(
        self, warn_only: bool = False, logfile: Callable = safe_print
    ) -> None:
        """Fix (or warn about) <= zero measurements.

        If XYZ/Lab = 0, the sample gets removed. If only one component of
        XYZ/Lab is <= 0, it gets fudged so that the component is nonzero
        (because otherwise, Argyll's colprof will remove it, which can have bad
        effects if it's an 'essential' sample)

        Args:
            warn_only (bool): If True, only warn about the issue, do not fix it.
            logfile (callable): A function to log messages to, defaults to
                safe_print.
        """
        color_rep = (self.queryv1("COLOR_REP") or b"").split(b"_")
        data = self.queryv1("DATA")
        if len(color_rep) != 2 or not data:
            return

        # Check for XYZ/Lab = 0 readings
        cie_labels = self._get_cie_labels(color_rep)
        device_labels = self._generate_device_labels(color_rep)
        remove = []
        for _key in data:
            sample = data[_key]
            cie_values = [sample[label.decode("utf-8")] for label in cie_labels]
            # Check if zero
            device_label_values = sample.queryv1(device_labels)
            if [v for v in cie_values if v]:
                # Not all zero. Check if some component(s) equal or below zero
                if min(cie_values) <= 0:
                    for label in cie_labels:
                        if sample[label.decode("utf-8")] > 0:
                            continue
                        if warn_only:
                            self._warn_sample_below_threshold(
                                logfile, color_rep, sample, device_label_values, label
                            )
                        else:
                            # Fudge to be nonzero
                            sample[label.decode("utf-8")] = 0.000001
                            self._log_fudged_sample(
                                logfile, color_rep, sample, device_label_values, label
                            )
                continue
            # All zero
            device_values = [sample[label.decode("utf-8")] for label in device_labels]
            if not max(device_values):
                # Skip device black
                continue
            if warn_only:
                self._warn_zero_measurement(
                    logfile, color_rep, sample, device_label_values
                )
            else:
                # Queue sample for removal
                remove.insert(0, sample)
                self._log_sample_removal(
                    logfile, color_rep, sample, device_label_values
                )
        for sample in remove:
            # Remove sample
            data.pop(sample)

    def _get_cie_labels(self, color_rep: tuple) -> list:
        """Generate CIE labels based on the color representation.

        Args:
            color_rep (tuple): The color representation of the sample.

        Returns:
            list: A list of CIE labels for the color representation.
        """
        cie_labels = []
        for i in range(len(color_rep[1])):
            channel = color_rep[1][i : i + 1]
            cie_labels.append(color_rep[1] + b"_" + channel)
            if color_rep[1] == b"LAB":
                # Only check L* for zero values
                break
        return cie_labels

    def _generate_device_labels(self, color_rep: tuple) -> list:
        """Generate device labels based on the color representation.

        Args:
            color_rep (tuple): The color representation of the sample.

        Returns:
            list: A list of device labels for the color representation.
        """
        device_labels = []
        for i in range(len(color_rep[0])):
            channel = color_rep[0][i : i + 1]
            device_labels.append(color_rep[0] + b"_" + channel)
        return device_labels

    def _warn_sample_below_threshold(
        self,
        logfile: Callable,
        color_rep: tuple,
        sample: CGATS,
        device_label_values: bytes,
        label: bytes,
    ) -> None:
        """Log a warning for a sample with a measurement below or equal to zero.

        Args:
            logfile (callable): A function to log messages to, if None is given
                this function does nothing.
            color_rep (tuple): The color representation of the sample.
            sample (CGATS): The sample that is being removed.
            device_label_values (bytes): The device label values of the sample.
            label (bytes): The label of the measurement that is below or equal
                to zero.
        """
        if not logfile:
            return
        logfile.write(
            "Warning: Sample ID {:d} ({} {}) has {} <= 0!\n".format(
                int(sample.SAMPLE_ID),
                color_rep[0],
                " ".join(
                    device_label_values.decode("utf-8").split()
                    if device_label_values
                    else [""]
                ),
                label.decode("utf-8"),
            )
        )

    def _log_fudged_sample(
        self,
        logfile: Callable,
        color_rep: tuple,
        sample: CGATS,
        device_label_values: bytes,
        label: bytes,
    ) -> None:
        """Log a message for a sample that was fudged to be non-zero.

        Args:
            logfile (callable): A function to log messages to, if None is given
                this function does nothing.
            color_rep (tuple): The color representation of the sample.
            sample (CGATS): The sample that is being removed.
            device_label_values (bytes): The device label values of the sample.
            label (bytes): The label of the measurement that was fudged to be
                non-zero.
        """
        if not logfile:
            return
        logfile.write(
            "Fudged sample ID {:d} ({} {}) {} to be non-zero\n".format(
                int(sample.SAMPLE_ID),
                color_rep[0],
                " ".join(
                    device_label_values.decode("utf-8").split()
                    if device_label_values
                    else [""]
                ),
                label.decode("utf-8"),
            )
        )

    def _warn_zero_measurement(
        self,
        logfile: Callable,
        color_rep: tuple,
        sample: CGATS,
        device_label_values: bytes,
    ) -> None:
        """Log a warning for a sample with zero measurements.

        Args:
            logfile (callable): A function to log messages to, if None is given
                this function does nothing.
            color_rep (tuple): The color representation of the sample.
            sample (CGATS): The sample that is being removed.
            device_label_values (bytes): The device label values of the sample.
        """
        if not logfile:
            return

        logfile.write(
            "Warning: Sample ID {} ({} {}) has {} = 0!\n".format(
                sample.SAMPLE_ID,
                color_rep[0],
                " ".join(
                    device_label_values.decode("utf-8").split()
                    if device_label_values
                    else [""]
                ),
                color_rep[1],
            )
        )

    def _log_sample_removal(
        self,
        logfile: Callable,
        color_rep: tuple,
        sample: CGATS,
        device_label_values: bytes,
    ) -> None:
        """Log the removal of a sample with zero measurements.

        Args:
            logfile (callable): A function to log messages to, if None is given
                this function does nothing.
            color_rep (tuple): The color representation of the sample.
            sample (CGATS): The sample that is being removed.
            device_label_values (bytes): The device label values of the sample.
        """
        if not logfile:
            return
        logfile.write(
            "Removed sample ID {:d} ({} {}) with {} = 0\n".format(
                int(sample.SAMPLE_ID),
                color_rep[0],
                " ".join(
                    device_label_values.decode("utf-8").split()
                    if device_label_values
                    else [""]
                ),
                color_rep[1],
            )
        )

    def fix_device_values_scaling(self, color_rep: None | str = None) -> int:
        """Attempt to fix device value scaling so that max = 100.

        Args:
            color_rep (Nont | str): The color representation to fix. If None,
                all device values are fixed. Defaults to None.

        Returns:
            int: The number of fixed DATA sections.
        """
        fixed = 0
        for labels in get_device_value_labels(color_rep):
            for dataset in self.query(b"DATA").values():
                for item in dataset.queryi(labels).values():
                    for label in labels:
                        if item[label] > 100:
                            dataset.scale_device_values(color_rep=color_rep)
                            fixed += 1
                            break
        return fixed

    def normalize_to_y_100(self) -> bool:
        """Scale XYZ values so that RGB 100 = Y 100.

        Returns:
            bool: True if normalization was applied, False otherwise.
        """
        if "DATA" in self:
            white_cie = self.get_white_cie()
            if white_cie and "XYZ_Y" in white_cie:
                white_y = white_cie["XYZ_Y"]
                if white_y != 100:
                    self.add_keyword(
                        "LUMINANCE_XYZ_CDM2",
                        "{:.4f} {:.4f} {:.4f}".format(
                            white_cie["XYZ_X"], white_cie["XYZ_Y"], white_cie["XYZ_Z"]
                        ),
                    )
                    for sample in self.DATA.values():
                        for label in "XYZ":
                            v = sample["XYZ_" + label]
                            sample["XYZ_" + label] = v / white_y * 100
                self.add_keyword("NORMALIZED_TO_Y_100", "YES")
                return True
        return False

    def quantize_device_values(
        self, bits: int = 8, quantizer: Callable = round
    ) -> None:
        """Quantize device values to n bits.

        Args:
            bits (int): The number of bits to quantize to. Defaults to 8.
            quantizer (callable): A function to use for quantization. Defaults
                to round, which is suitable for most cases.
        """
        q = 2**bits - 1.0
        for data in self.queryv("DATA").values():
            if data.parent.type == b"CAL":
                maxv = 1.0
                digits = 8
            else:
                maxv = 100.0
                # Assuming 0..100, 4 decimal digits is
                # enough for roughly 19 bits integer
                # device values
                digits = 4
            color_rep = (data.parent.queryv1("COLOR_REP") or b"").split(b"_")[0]
            for labels in get_device_value_labels(color_rep):
                for item in data.queryi(labels).values():
                    for label in labels:
                        item[label] = round(
                            quantizer(item[label] / maxv * q) / q * maxv, digits
                        )

    def scale_device_values(
        self, factor: float = 100.0 / 255, color_rep: None | str = None
    ) -> None:
        """Scale device values by multiplying with factor.

        Args:
            factor (float): The factor to scale the device values by. Defaults
                to 100.0 / 255, which is the scaling from 8-bit to 100% device
                values.
            color_rep (None | str): The color representation to scale. If None, all
                device values are scaled. Defaults to None.
        """
        for labels in get_device_value_labels(color_rep):
            for data in self.queryv("DATA").values():
                for item in data.queryi(labels).values():
                    for label in labels:
                        item[label] *= factor

    def adapt(
        self,
        whitepoint_source: None | str = None,
        whitepoint_destination: None | str = None,
        cat: str = "Bradford",
    ) -> int:
        """Perform chromatic adaptation if possible (needs XYZ or LAB).

        Args:
            whitepoint_source (None | str): The source whitepoint to adapt
                from. Defaults to None, which uses the whitepoint of the first
                DATA section.
            whitepoint_destination (None | str): The destination whitepoint to
                adapt to. Defaults to "D50".
            cat (str): The chromatic adaptation transform to use. Defaults to
                "Bradford".

        Returns:
            int: The number of affected DATA sections.
        """
        sections = 0
        for dataset in self.query("DATA").values():
            if not dataset.get_cie_data_format():
                continue
            if not whitepoint_source:
                whitepoint_source = dataset.get_white_cie("XYZ")
            if not whitepoint_source:
                continue
            sections += 1
            for item in dataset.queryv1("DATA").values():
                if "XYZ_X" in item:
                    x, y, z = item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"]
                else:
                    x, y, z = colormath.Lab2XYZ(
                        item["LAB_L"], item["LAB_A"], item["LAB_B"], scale=100
                    )
                x, y, z = colormath.adapt(
                    x, y, z, whitepoint_source, whitepoint_destination, cat
                )
                if "LAB_L" in item:
                    (
                        item["LAB_L"],
                        item["LAB_A"],
                        item["LAB_B"],
                    ) = colormath.XYZ2Lab(x, y, z)
                if "XYZ_X" in item:
                    item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"] = x, y, z
        return sections

    def apply_bpc(
        self, bp_out: tuple[float, float, float] = (0, 0, 0), weight: bool = False
    ) -> int:
        """Apply black point compensation.

        Scales XYZ so that black (RGB 0) = zero.
        Needs a CGATS structure with RGB and XYZ data and atleast one black and
        white patch.

        Args:
            bp_out (tuple[float, float, float]): The output black point to use.
                Defaults to (0, 0, 0).
            weight (bool): If True, use the weight method for BPC, otherwise
                use the blend method. Defaults to False.

        Returns:
            int: The number of DATA sections that were affected by the BPC.
        """
        n = 0
        for dataset in self.query("DATA").values():
            is_lab, labels, data, max_v, black, white = (
                self._extract_white_black_from_data(dataset)
            )
            if black is None or white is None:
                # Can't apply bpc
                continue

            # Apply black point compensation
            n += 1
            for i in data:
                values = list(data[i].queryv1(labels).values())
                if is_lab:
                    values = colormath.Lab2XYZ(*values)
                else:
                    values = [v / max_v for v in values]
                if weight:
                    values = colormath.apply_bpc(
                        values[0], values[1], values[2], black, bp_out, white, weight
                    )
                else:
                    values = colormath.blend_blackpoint(
                        values[0], values[1], values[2], black, bp_out, white
                    )
                values = [v * max_v for v in values]
                if is_lab:
                    values = colormath.XYZ2Lab(*values)
                for j, label in enumerate(labels):
                    if is_lab and j > 0:
                        data[i][label] = values[j]
                    else:
                        data[i][label] = max(0.0, values[j])
        return n

    def _extract_white_black_from_data(
        self, dataset: CGATS
    ) -> tuple[bool, tuple, CGATS, float, list, list]:
        """Extract white and black points from the dataset.

        Args:
            dataset (CGATS): The dataset to extract white and black points from.

        Returns:
            tuple[bool, tuple, CGATS, float, list, list]: A tuple containing:
                - is_lab (bool): True if the dataset is in Lab color space.
                - labels (tuple): The labels for the color channels.
                - data (CGATS): The data object containing the color values.
                - max_v (float): The maximum value for scaling.
                - black (list): The black point values.
                - white (list): The white point values.
        """
        if dataset.type.strip() == b"CAL":
            is_lab = False
            labels = ("RGB_R", "RGB_G", "RGB_B")
            data = dataset.queryi(labels)

            # Get black
            black1 = data.queryi1({"RGB_I": 0})
            # Get white
            white1 = data.queryi1({"RGB_I": 1})
            if not black1 or not white1:
                # Can't apply bpc
                return is_lab, labels, data, None, None, None

            black = []
            white = []
            for label in labels:
                black.append(black1[label])
                white.append(white1[label])
            max_v = 1.0
        else:
            is_lab = b"_LAB" in (dataset.queryv1("COLOR_REP") or b"")
            labels = (
                ("LAB_L", "LAB_A", "LAB_B") if is_lab else ("XYZ_X", "XYZ_Y", "XYZ_Z")
            )
            # 0: Index of L* in labels
            # 1: Index of Y in labels
            index = 0 if is_lab else 1
            data = dataset.queryi(("RGB_R", "RGB_G", "RGB_B", *labels))

            # Get blacks
            blacks = data.queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
            # Get whites
            whites = data.queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
            if not blacks or not whites:
                # Can't apply bpc
                return is_lab, labels, data, max_v, None, None

            black = [0, 0, 0]
            white = [0, 0, 0]

            for i in blacks:
                if blacks[i][labels[index]] > black[index]:
                    for j, label in enumerate(labels):
                        black[j] = blacks[i][label]

            for i in whites:
                if whites[i][labels[index]] > white[index]:
                    for j, label in enumerate(labels):
                        white[j] = whites[i][label]
            if is_lab:
                max_v = 100.0
                black = colormath.Lab2XYZ(*black)
                white = colormath.Lab2XYZ(*white)
            else:
                max_v = white[1]
                black = [v / max_v for v in black]
                white = [v / max_v for v in white]

        return is_lab, labels, data, max_v, black, white

    def get_white_cie(
        self, colorspace: None | str = None
    ) -> None | tuple[float, float, float] | dict:
        """Get the 'white' from the CIE values (if any).

        Args:
            colorspace (str, optional): The colorspace to return the white
                point in. If None, returns a dict with XYZ or Lab values.

        Returns:
            None | tuple[float, float, float] | dict: The white point in the
                specified colorspace or a dict with XYZ or Lab values.
        """
        if not (data_format := self.get_cie_data_format()):
            return None

        if "RGB_R" in list(data_format.values()):
            white = {"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}
        elif "CMYK_C" in list(data_format.values()):
            white = {"CMYK_C": 0, "CMYK_M": 0, "CMYK_Y": 0, "CMYK_K": 0}
        else:
            white = None

        if white:
            white = self.queryi1(white)
        if not white:
            white = self._get_white_cie_from_luminance_or_approx_white_point()
            if not white:
                return None
        return self._get_white_cie_from_xyz_or_lab(white, colorspace=colorspace)

    def _get_white_cie_from_luminance_or_approx_white_point(self) -> None | dict:
        """Get the white point from LUMINANCE_XYZ_CDM2 or APPROX_WHITE_POINT.

        Returns:
            None | dict: None if no white point is found, otherwise a dict
                with keys "XYZ_X", "XYZ_Y", and "XYZ_Z" representing the white
                point in CIE XYZ format.
        """
        for key in ("LUMINANCE_XYZ_CDM2", "APPROX_WHITE_POINT"):
            if not (white := self.queryv1(key)):
                continue
            try:
                white = [float(v) for v in white.split()]
            except ValueError:
                white = None
            else:
                if len(white) == 3:
                    white = [v / white[1] * 100 for v in white]
                    white = {
                        "XYZ_X": white[0],
                        "XYZ_Y": white[1],
                        "XYZ_Z": white[2],
                    }
                    break
                white = None
        return white

    def _get_white_cie_from_xyz_or_lab(
        self, white: dict, colorspace: None | str = None
    ) -> None | tuple[float, float, float] | dict:
        """Get the white point in the specified colorspace.

        Args:
            white (dict): The white point in XYZ or Lab format.
            colorspace (str, optional): The colorspace to return the white
                point in. If None, this function will return the white point as
                it is.

        Returns:
            None | tuple[float, float, float] | dict: The white point in the
                specified colorspace or a dict with XYZ or Lab values if the
                given colorspace is not "Lab" or "XYZ" or None if the white
                point is not given.
        """
        if white and (
            ("XYZ_X" in white and "XYZ_Y" in white and "XYZ_Z" in white)
            or ("LAB_L" in white and "LAB_B" in white and "LAB_B" in white)
        ):
            if colorspace == "XYZ":
                if "XYZ_X" in white:
                    return white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
                return colormath.Lab2XYZ(
                    white["LAB_L"], white["LAB_A"], white["LAB_B"], scale=100
                )
            if colorspace == "Lab":
                if "LAB_L" in white:
                    return white["LAB_L"], white["LAB_A"], white["LAB_B"]
                return colormath.XYZ2Lab(white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"])
            return white
        return None

    def get_cie_data_format(self) -> None | bytes:
        """Check if DATA_FORMAT defines any CIE XYZ or LAB columns.

        Returns:
            None | bytes: The DATA_FORMAT on success or None on failure.
        """
        if data_format := self.queryv1("DATA_FORMAT"):
            cie = {}
            for channel in (b"LAB_L", b"LAB_A", b"LAB_B"):
                cie[channel] = channel in list(data_format.values())
            if len(list(cie.values())) in [0, 3]:
                for channel in (b"XYZ_X", b"XYZ_Y", b"XYZ_Z"):
                    cie[channel] = channel in list(data_format.values())
                if len([v for v in iter(cie.values()) if v is not False]) in {3, 6}:
                    return data_format
        return None

    pop = remove

    def write(self, stream_or_filename: None | str | BinaryIO = None) -> None:
        """Write CGATS text to stream.

        Args:
            stream_or_filename (str | BinaryIO, optional): The stream
                or filename to write the CGATS data to. If None, uses the
                filename of the CGATS object. Defaults to None.
        """
        if not stream_or_filename:
            stream_or_filename = self.filename
        if isinstance(stream_or_filename, str):
            with open(stream_or_filename, "wb") as stream:
                stream.write(bytes(self))
        else:
            stream = stream_or_filename
            # This seems like a duplicate, but reduces complexity of the code
            stream.write(bytes(self))
