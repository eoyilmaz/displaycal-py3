"""Generic container helpers used by ICC profile tag parsing.

These are standalone data structures (attribute-accessible dicts, list
subclasses, an interpolator) with no dependency on the ICC tag classes that
use them.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, SupportsIndex

if TYPE_CHECKING:

    from typing import Self


class CRInterpolation:
    """Catmull-Rom interpolation.

    Curve passes through the points exactly, with neighbouring points
    influencing curvature.points[] should be at least 3 points long.

    Args:
        points (list[float]): A list of points to interpolate. The list should
            contain at least 3 points, and each point should be a float value.
    """

    def __init__(self, points: list[float]) -> None:
        self.points = points

    def __call__(self, pos: float) -> float:
        """Interpolate the value at the given position.

        Args:
            pos (float): The position to interpolate the value for, in the range
                [0, len(points) - 1].

        Returns:
            float: The interpolated value at the given position.
        """
        lbound = int(math.floor(pos) - 1)
        ubound = int(math.ceil(pos) + 1)
        t = pos % 1.0
        if abs((lbound + 1) - pos) < 0.0001:
            # sitting on a datapoint, so just return that
            return self.points[lbound + 1]
        if lbound < 0:
            p = self.points[: ubound + 1]
            # extend to the left linearly
            while len(p) < 4:
                p.insert(0, p[0] - (p[1] - p[0]))
        else:
            p = self.points[lbound : ubound + 1]
            # extend to the right linearly
            while len(p) < 4:
                p.append(p[-1] - (p[-2] - p[-1]))
        t2 = t * t
        return 0.5 * (
            (2 * p[1])
            + (-p[0] + p[2]) * t
            + ((2 * p[0]) - (5 * p[1]) + (4 * p[2]) - p[3]) * t2
            + (-p[0] + (3 * p[1]) - (3 * p[2]) + p[3]) * (t2 * t)
        )


class ADict(dict):
    """Convenience class for dictionary key access via attributes.

    Instead of writing aodict[key], you can also write aodict.key
    """

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Get the attribute with the given name.

        Args:
            name (str): The name of the attribute to get.
        """
        if name in self:
            return self[name]
        return self.__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set the attribute with the given name to the given value.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        self[name] = value


class AODict(ADict):
    """Convenience class for dictionary key access via attributes."""

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set the attribute with the given name to the given value.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        if name == "_keys":
            object.__setattr__(self, name, value)
        else:
            self[name] = value


class DictList(list):
    """ICC dictType Tag list."""

    def __getitem__(self, key: slice | SupportsIndex) -> Any:  # noqa: ANN401
        """Get item from list.

        Args:
            key (slice | SupportsIndex): Key of the item.

        Returns:
            Any: Value of the item.
        """
        for item in self:
            if item[0] == key:
                return item
        raise KeyError(key)

    def __setitem__(self, key: slice | SupportsIndex, value: Any) -> None:  # noqa: ANN401
        """Set item in list.

        Args:
            key (slice | SupportsIndex): Key of the item.
            value (Any): Value of the item.
        """
        if not isinstance(value, DictListItem):
            self.append(DictListItem((key, value)))


class DictListItem(list):
    """ICC dictType Tag item."""

    def __iadd__(self, value: Any) -> Self:  # noqa: ANN401
        """Add value to the last item in the list.

        Args:
            value (Any): Value to add.

        Returns:
            DictListItem: The updated list item.
        """
        self[-1] += value
        return self
