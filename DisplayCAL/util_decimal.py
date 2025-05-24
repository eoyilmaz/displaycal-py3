"""This module provides utility functions for working with decimal numbers.
It includes functions for converting floats to decimals with precision
handling and for stripping trailing zeros from numeric representations.
"""

import contextlib
import decimal
import math


def float2dec(f: float, digits: int = 10) -> decimal.Decimal:
    """Convert a float to a decimal with specified precision.

    If the float has more than the specified number of digits after the
    decimal point, it will be rounded to the nearest integer.

    If the float has exactly the specified number of digits after the
    decimal point, it will be rounded to the nearest integer if the last
    digit is 9, and to the nearest integer if the last digit is 0.

    Args:
        f (float): The float to convert.
        digits (int): The number of decimal digits to consider.
            Default is 10.

    Returns:
        decimal.Decimal: The converted decimal number.
    """
    parts = str(f).split(".")
    if len(parts) > 1:
        if parts[1][:digits] == "9" * digits:
            f = math.ceil(f)
        elif parts[1][:digits] == "0" * digits:
            f = math.floor(f)
    return decimal.Decimal(str(f))


def stripzeros(n):
    """Strip zeros and convert to decimal.

    Will always return the shortest decimal representation
    (1.0 becomes 1, 1.234567890 becomes 1.23456789).

    """
    n = f"{n:.10f}" if isinstance(n, (float, int)) else str(n)
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    with contextlib.suppress(decimal.InvalidOperation):
        n = decimal.Decimal(n)
    return n
