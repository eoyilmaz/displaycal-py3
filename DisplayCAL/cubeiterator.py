"""Classes for working with and iterating over 3D data cubes.

It includes functionality to define a cube, access its elements, and iterate
through its contents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


class Cube3D:
    """A 3D cube of data.

    This class provides functionality to define a cube, access its elements,
    and iterate through its contents. It allows for specifying the size of the
    cube and the range of indices to be used.

    Args:
        size (int): The size of the cube along each dimension. Default is 65.
        start (int): The starting index for the cube. Default is 0.
        end (None | int, optional): The ending index for the cube. If not
            specified, it defaults to the total number of entries in the cube,
            which is `size**3`. If specified, it must be greater than or equal
            to `start`. Default is None.

    Raises:
        TypeError: If `start` or `end` is not an integer.
        ValueError: If `start` or `end` is out of range or if `end` is less
            than `start`.
    """

    def __init__(self, size: int = 65, start: int = 0, end: None | int = None) -> None:
        num_entries = size**3
        if end is None:
            end = num_entries

        if not isinstance(start, int):
            raise TypeError(
                f"integer start argument expected, got {start.__class__.__name__}"
            )

        if not isinstance(end, int):
            raise TypeError(
                f"integer end argument expected, got {end.__class__.__name__}"
            )

        start = self._clamp(start, 0, num_entries, -1)
        end = self._clamp(end, 0, num_entries, -1)

        if start == -1:
            raise ValueError(f"start argument {start:.0f} out of range")

        if end == -1:
            raise ValueError(f"end argument {end:.0f} out of range")

        self._size = size
        self._start = start
        self._len = end - start

    def get(
        self, i: int, default: None | tuple[int, int, int] = None
    ) -> None | tuple[int, int, int]:
        """Return the item at the specified index or a default value.

        Args:
            i (int): The index of the item to return.
            default (None, optional)): The value to return if the index is out
                of range.

        Returns:
            None | tuple[int, int, int]: The item at the specified index or the
                default value if the index is out of range.
        """
        if i < 0:
            i = self._len + i
        if i < 0 or i > self._len - 1:
            return default
        return self[i]

    def index(self, item: tuple[int, int, int]) -> int:
        """Return the index of the specified item in the cube.

        Args:
            item (tuple[int, int, int]): The item to find the index of.

        Raises:
            ValueError: If the item is not found in the cube.

        Returns:
            int: The index of the item in the cube.
        """
        (c0, c1, c2) = item
        if (c0, c1, c2) not in self:
            raise ValueError(f"{(c0, c1, c2)!r} not in {self!r}")
        i = c0 * self._size**2 + c1 * self._size + c2
        return int(i) - self._start

    def _clamp(
        self,
        v: int,
        lower: int = 0,
        upper: None | int = None,
        fallback: None | int = None,
    ) -> int:
        """Clamp a value to a specified range.

        Args:
            v (int): The value to clamp.
            lower (int): The lower bound of the range. Default is 0.
            upper (None | int, optional): The upper bound of the range. If not
                specified, it defaults to the length of the cube.
            fallback (None | int, optional): A fallback value to use if `v` is
                out of range. If not specified, it defaults to `lower` if `v`
                is less than `lower`, or `upper` if `v` is greater than
                `upper`.

        Returns:
            int: The clamped value.
        """
        if not upper:
            upper = self._len
        if v < lower:
            v = fallback or lower if v < -upper else upper + v
        elif v > upper:
            v = fallback or upper
        return v

    def __contains__(self, other: tuple[int, int, int]) -> bool:
        """Check if the cube contains the specified item.

        Args:
            other (tuple): The item to check.

        Returns:
            bool: True if the cube contains the item, False otherwise.
        """
        (c0, c1, c2) = other
        return (
            c0 == int(c0)
            and c1 == int(c1)
            and c2 == int(c2)
            and max(c0, c1, c2) < self._size
            and self._start
            <= c0 * self._size**2 + c1 * self._size + c2
            < self._len + self._start
        )

    def __getitem__(self, i: int) -> tuple[int, int, int]:
        """Return the item at the specified index.

        Args:
            i (int): The index of the item to return.

        Raises:
            IndexError: If the index is out of range.

        Returns:
            tuple[int, int, int]: The item at the specified index.
        """
        oi = i
        if i < 0:
            i = self._len + i
        if i < 0 or i > self._len - 1:
            raise IndexError(f"index {oi} out of range")
        i += self._start
        return (
            i // self._size // self._size,
            i // self._size % self._size,
            i % self._size,
        )

    def __len__(self) -> int:
        """Return the length of the cube.

        Returns:
            int: The length of the cube.
        """
        return self._len

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: The string representation of the object.
        """
        return "{}(size={:.0f}, start={:.0f}, end={:.0f})".format(  # noqa: UP032
            self.__class__.__name__,
            self._size,
            self._start,
            self._start + self._len,
        )


class Cube3DIterator(Cube3D):
    """An iterator for the Cube3D class.

    This iterator is actually slightly slower especially with large cubes
    than using iter(<Cube3D instance>).
    """

    def __init__(self, *args, **kwargs) -> None:
        Cube3D.__init__(self, *args, **kwargs)
        self._next = 0

    def __iter__(self) -> Self:
        """Return the object itself as an iterator."""
        return self

    def __next__(self) -> tuple[int, int, int]:
        """Return the next item in the iteration.

        Raises:
            StopIteration: If there are no more items to iterate over.

        Returns:
            tuple[int, int, int]: The next item in the iteration.
        """
        if self._next == self._len:
            raise StopIteration
        result = self[self._next]
        self._next += 1
        return result
