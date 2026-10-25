"""Base ICC profile tag class and its zero-dependency tag types.

`LazyLoadTagAODict` is grouped here alongside `ICCProfileTag` (rather than in
`icc_profile.structures`, per the original plan) because it dispatches on the
tag registries (`TAG_SIGNATURE_TO_TAG`/`TYPE_SIGNATURE_TO_TYPE`) and raises
`ICCProfileInvalidError`, neither of which exist until every tag type module
has been extracted. It resolves those via a deferred import, the same
pattern used by `icc_profile.codecs.videoCardGamma()`.
"""

from __future__ import annotations

import datetime
from collections import UserString
from typing import TYPE_CHECKING, Any

from DisplayCAL import colormath
from DisplayCAL.icc_profile.codecs import (
    dateTimeNumber,
    s15Fixed16Number,
    s15Fixed16Number_tohex,
)
from DisplayCAL.icc_profile.constants import FS_ENC
from DisplayCAL.icc_profile.structures import AODict

if TYPE_CHECKING:
    from typing import Self

    from DisplayCAL.icc_profile import ICCProfile


class ICCProfileTag:
    """Base class for ICC profile tags.

    Args:
        tagData (bytes): The data of the tag.
        tagSignature (str): The signature of the tag.
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        self.tagData = tagData
        self.tagSignature = tagSignature

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set attribute with the given name to the given value.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        if not isinstance(self, dict) or name in ("_keys", "tagData", "tagSignature"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def __repr__(self) -> str:
        """Return the string representation of the object.

        t.__repr__() <==> repr(t).

        Returns:
            str: The string representation of the object.
        """
        if isinstance(self, dict):
            return dict.__repr__(self)
        if isinstance(self, UserString):
            return UserString.__repr__(self)
        if isinstance(self, list):
            return list.__repr__(self)
        cls = self.__class__
        if not self:
            return f"{cls.__module__}.{cls.__name__}()"
        return f"{cls.__module__}.{cls.__name__}({self.tagData!r})"


class Text(ICCProfileTag, bytes):
    """Text tag class which is a bytes type and handles str conversion.

    Args:
        seq (bytes): The byte sequence representing the text tag.
    """

    def __init__(self, seq: bytes) -> None:
        super().__init__(tagData=seq, tagSignature=b"")
        self.data = seq

    def __str__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: The string representation of the object.
        """
        return self.data.decode(FS_ENC, errors="replace")


class DateTimeType(ICCProfileTag, datetime.datetime):
    """ICC DateTimeType tag.

    Args:
        tagData (bytes): The raw tag data containing the date and time.
        tagSignature (str): The signature of the tag (not used here).
    """

    def __new__(cls, tagData: bytes, tagSignature: str) -> datetime.datetime:  # noqa: N803
        """Create a new DateTimeType instance.

        Args:
            cls: The class to instantiate.
            tagData: The raw tag data containing the date and time.
            tagSignature: The signature of the tag (not used here).

        Returns:
            datetime.datetime: A new instance of datetime.datetime.
        """
        dt = dateTimeNumber(tagData[8:20])
        return datetime.datetime.__new__(
            cls, dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
        )


class S15Fixed16ArrayType(ICCProfileTag, list):
    """ICC s15Fixed16ArrayType tag.

    Args:
        tagData (bytes, optional): Raw tag data. Defaults to None.
        tagSignature (str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if tagData:
            data = tagData[8:]
            while data:
                self.append(s15Fixed16Number(data[0:4]))
                data = data[4:]

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data formatted as bytes.
        """
        tag_data = [b"sf32", b"\0" * 4]
        tag_data.extend(s15Fixed16Number_tohex(value) for value in self)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tag_data: bytes) -> None:  # noqa: N802
        """Set raw tag data.

        Does nothing, as this tag is read-only.

        Args:
            tag_data (bytes): Raw tag data to set.
        """


class TagData:
    """ICC tag data type.

    Args:
        tagData (bytes): The raw tag data.
        offset (int): The offset in the tag data where this tag starts.
        size (int): The size of the tag data.
    """

    def __init__(self, tagData: bytes, offset: int, size: int) -> None:  # noqa: N803
        self.tagData = tagData
        self.offset = offset
        self.size = size

    def __contains__(self, item: bytes) -> bool:
        """Check if the item is in the tag data.

        Args:
            item (bytes): The item to check for.

        Returns:
            bool: True if the item is in the tag data, False otherwise.
        """
        return item in bytes(self)

    def __bytes__(self) -> bytes:
        """Return the bytes representation of the object.

        Returns:
            bytes: Bytes representation of the object.
        """
        return self.tagData[self.offset : self.offset + self.size]


class XYZNumber(AODict):
    """XYZNumber class.

    Byte Offset Content Encoded as...
    0..3   CIE X   s15Fixed16Number
    4..7   CIE Y   s15Fixed16Number
    8..11  CIE Z   s15Fixed16Number

    Args:
        binaryString (None | bytes, optional): Binary string containing XYZ values.
    """

    def __init__(self, binaryString: None | bytes = None) -> None:  # noqa: N803
        if binaryString is None:
            binaryString = b"\0" * 12  # noqa: N806
        AODict.__init__(self)
        self.X, self.Y, self.Z = [
            s15Fixed16Number(chunk)
            for chunk in (binaryString[:4], binaryString[4:8], binaryString[8:12])
        ]

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: String representation of the object.
        """
        XYZ = []  # noqa: N806
        for key in self:
            value = self[key]
            XYZ.append(f"({key!r}, {value})")
        return "{}.{}([{}])".format(
            self.__class__.__module__,
            self.__class__.__name__,
            ", ".join(XYZ),
        )

    def adapt(
        self,
        whitepoint_source: None | float | str | list | tuple = None,
        whitepoint_destination: None | float | str | list | tuple = None,
        cat: str = "Bradford",
    ) -> XYZNumber:
        """Adapt XYZ values to a different white point.

        Args:
            whitepoint_source (None | float | str | list | tuple): Source white
                point, defaults to None.
            whitepoint_destination (None | float | str | list | tuple): Destination
                white point, defaults to None.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".

        Returns:
            XYZNumber: A new instance of XYZNumber with adapted values.
        """
        XYZ = self.__class__()  # noqa: N806
        XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(
            self.X, self.Y, self.Z, whitepoint_source, whitepoint_destination, cat
        )
        return XYZ

    def round(self, digits: int = 4) -> XYZNumber:
        """Round XYZ values to a specified number of digits.

        Args:
            digits (int, optional): Number of digits to round to. Defaults to 4.

        Returns:
            XYZNumber: A new instance of XYZNumber with rounded values.
        """
        XYZ = self.__class__()  # noqa: N806
        for key in self:
            XYZ[key] = round(self[key], digits)
        return XYZ

    def tohex(self) -> bytes:
        """Return the hexadecimal representation of the XYZ values.

        Returns:
            bytes: Hexadecimal string of the XYZ values.
        """
        data = [s15Fixed16Number_tohex(n) for n in list(self.values())]
        return b"".join(data)

    @property
    def hex(self) -> str:
        """Return the hexadecimal representation of the XYZ values.

        Returns:
            str: Hexadecimal string of the XYZ values.
        """
        return self.tohex()

    @property
    def Lab(self) -> tuple[float, float, float]:  # noqa: N802
        """Return Lab values relative to the profile.

        Returns:
            tuple[float, float, float]: A tuple containing the Lab values.
        """
        return colormath.XYZ2Lab(*[v * 100 for v in list(self.values())])

    @property
    def xyY(self) -> colormath.NumberTuple:  # noqa: N802
        """Return xyY values relative to the profile.

        Returns:
            colormath.NumberTuple: xyY values as a NumberTuple.
        """
        return colormath.NumberTuple(colormath.XYZ2xyY(self.X, self.Y, self.Z))


class XYZType(ICCProfileTag, XYZNumber):
    """XYZType class.

    This class represents the XYZ color space in ICC profiles.
    It inherits from ICCProfileTag and XYZNumber.
    """

    def __init__(
        self,
        tagData: bytes = b"\0" * 20,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        profile: None | ICCProfile = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        XYZNumber.__init__(self, tagData[8:20])
        self.profile = profile

    __repr__ = XYZNumber.__repr__

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set attribute value.

        Args:
            name (str): Name of the attribute to set.
            value (Any): Value to set the attribute to.
        """
        if name in ("_keys", "profile", "tagData", "tagSignature"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def adapt(
        self,
        whitepoint_source: None | float | str | list | tuple = None,
        whitepoint_destination: None | float | str | list | tuple = None,
        cat: None | str = None,
    ) -> XYZType:
        """Adapt XYZ values to a different white point.

        Args:
            whitepoint_source (None | float | str | list | tuple, optional):
                Source white point. Defaults to None.
            whitepoint_destination (None | float | str | list | tuple, optional):
                Destination white point. Defaults to None.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".

        Returns:
            XYZType: A new instance of XYZType with adapted values.
        """
        if cat is None:
            if self.profile and isinstance(
                self.profile.tags.get("arts"), ChromaticAdaptionTag
            ):
                cat = self.profile.tags.arts
            else:
                cat = "Bradford"
        XYZ = self.__class__(profile=self.profile)  # noqa: N806
        XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(
            self.X, self.Y, self.Z, whitepoint_source, whitepoint_destination, cat
        )
        return XYZ

    @property
    def ir(self) -> Self | XYZType:
        """Get illuminant-relative values."""
        pcs_illuminant = list(self.profile.illuminant.values())
        if b"chad" in self.profile.tags and self.profile.creator != b"appl":
            # Apple profiles have a bug where they contain a 'chad' tag,
            # but the media white is not under PCS illuminant
            if self is self.profile.tags.wtpt:
                XYZ = self.__class__(profile=self.profile)  # noqa: N806
                XYZ.X, XYZ.Y, XYZ.Z = list(self.values())
            else:
                # Go from XYZ mediawhite-relative under PCS illuminant to XYZ
                # under PCS illuminant
                if isinstance(self.profile.tags.get("arts"), ChromaticAdaptionTag):
                    cat = self.profile.tags.arts
                else:
                    cat = "XYZ scaling"
                XYZ = self.adapt(  # noqa: N806
                    pcs_illuminant, list(self.profile.tags.wtpt.values()), cat=cat
                )
            # Go from XYZ under PCS illuminant to XYZ illuminant-relative
            XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * list(XYZ.values())
            return XYZ
        if self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")):
            # For profiles without 'chad' tag, the white/black point should
            # already be illuminant-relative
            return self
        if "chad" in self.profile.tags:
            XYZ = self.__class__(profile=self.profile)  # noqa: N806
            # Go from XYZ under PCS illuminant to XYZ illuminant-relative
            XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * list(
                self.values()
            )
            return XYZ
        # Go from XYZ under PCS illuminant to XYZ illuminant-relative
        return self.adapt(pcs_illuminant, list(self.profile.tags.wtpt.values()))

    @property
    def pcs(self) -> Self | XYZType:
        """Get PCS-relative values."""
        if self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")) and (
            "chad" not in self.profile.tags or self.profile.creator == b"appl"
        ):
            # Apple profiles have a bug where they contain a 'chad' tag,
            # but the media white is not under PCS illuminant
            if "chad" in self.profile.tags:
                XYZ = self.__class__(profile=self.profile)  # noqa: N806
                XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad * list(self.values())
                return XYZ
            pcs_illuminant = list(self.profile.illuminant.values())
            return self.adapt(list(self.profile.tags.wtpt.values()), pcs_illuminant)
        # Values should already be under PCS illuminant
        return self

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data containing XYZ values.
        """
        tag_data = [b"XYZ ", b"\0" * 4]
        tag_data.append(self.tohex())
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as XYZType is immutable.

        Args:
            tagData (bytes): Raw tag data to set.
        """

    @property
    def xyY(self) -> colormath.NumberTuple:  # noqa: N802
        """Get xyY values relative to the profile's reference white.

        Returns:
            colormath.NumberTuple: xyY values relative to the profile's
                reference white.
        """
        if self is self.profile.tags.get("bkpt"):
            ref = self.profile.tags.bkpt
        else:
            ref = self.profile.tags.wtpt
        return colormath.NumberTuple(
            colormath.XYZ2xyY(self.X, self.Y, self.Z, (ref.X, ref.Y, ref.Z))
        )


class ChromaticAdaptionTag(colormath.Matrix3x3, S15Fixed16ArrayType):
    """Chromatic Adaptation Matrix.

    The Chromatic Adaptation Matrix is a 3x3 matrix that transforms
    color values from one illuminant to another. It is used in
    color management systems to ensure that colors appear consistent
    across different devices and lighting conditions.

    The matrix is represented as a list of 3 rows, each containing
    3 values. The values are stored as s15Fixed16Number, which is a
    fixed-point representation with 15 bits for the integer part
    and 16 bits for the fractional part:

    Offset Content Encoded as:

        0..3   CIE X   s15Fixed16Number
        4..7   CIE Y   s15Fixed16Number
        8..11  CIE Z   s15Fixed16Number
        ...

    Args:
        tagData (None | bytes, optional): Binary data containing the chromatic
            adaptation matrix values. If None, an empty matrix is created.
        tagSignature (None | str, optional): Signature of the tag, typically
            "chad". If None, defaults to "chad".
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if tagData:
            data = tagData[8:]
            if data:
                matrix = []
                while data:
                    if len(matrix) == 0 or len(matrix[-1]) == 3:
                        matrix.append([])
                    matrix[-1].append(s15Fixed16Number(data[0:4]))
                    data = data[4:]
                self.update(matrix)
        else:
            self._reset()

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Args:
            tagData (bytes): Raw tag data containing the chromatic adaptation
                matrix values.

        Returns:
            bytes: Raw tag data containing the chromatic adaptation matrix
                values in the format expected by ICC profiles.
        """
        tag_data = [b"sf32", b"\0" * 4]
        tag_data.extend(
            s15Fixed16Number_tohex(column) for row in self for column in row
        )
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as ChromaticAdaptionTag is immutable.

        Args:
            tagData (bytes): Raw tag data to set.
        """

    def get_cat(self) -> None | str:
        """Compare to known CAT matrices and return matching name (if any)."""

        def q(v: int) -> float:
            """Quantize value to 16-bit fixed-point representation.

            Args:
                v (int): Value to quantize.

            Returns:
                float: Quantized value as float.
            """
            return s15Fixed16Number(s15Fixed16Number_tohex(v))

        for cat_name in colormath.CAT_MATRICES:
            cat_matrix = colormath.CAT_MATRICES[cat_name]
            if colormath.is_similar_matrix(self.applied(q), cat_matrix.applied(q), 4):
                return cat_name

        return None


class LazyLoadTagAODict(AODict):
    """Lazy-load (and parse) tag data on access.

    Args:
        profile (ICCProfile): The ICC profile this tag dictionary belongs to.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
    """

    def __init__(self, profile: ICCProfile, *args, **kwargs) -> None:
        self.profile = profile
        AODict.__init__(self)

    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        """Get the item with the given key.

        Args:
            key (str): The key to get the item for.

        Returns:
            Any: The item with the given key.
        """
        # Deferred import: the tag registries and ICCProfileInvalidError only
        # exist once every tag type module has been wired up in
        # DisplayCAL.icc_profile, which itself imports this module.
        from DisplayCAL.icc_profile import (
            TAG_SIGNATURE_TO_TAG,
            TYPE_SIGNATURE_TO_TYPE,
            ICCProfileInvalidError,
        )

        tag = AODict.__getitem__(self, key)
        if isinstance(tag, ICCProfileTag):
            # Return already parsed tag
            return tag
        # Load and parse tag data
        tag_signature = key
        type_signature, tag_data_offset, tag_data_size, tag_data = tag
        try:
            if tag_signature in TAG_SIGNATURE_TO_TAG:
                tag = TAG_SIGNATURE_TO_TAG[tag_signature](tag_data, tag_signature)
            elif type_signature in TYPE_SIGNATURE_TO_TYPE:
                args = tag_data, tag_signature
                if type_signature in (b"clrt", b"ncl2"):
                    args += (self.profile.connectionColorSpace,)
                    if type_signature == b"ncl2":
                        args += (self.profile.colorSpace,)
                elif type_signature in (b"XYZ ", b"mft2", b"curv", b"MS10", b"pseq"):
                    args += (self.profile,)
                tag = TYPE_SIGNATURE_TO_TYPE[type_signature](*args)
            else:
                tag = ICCProfileTag(tag_data, tag_signature)
        except Exception as exception:
            raise ICCProfileInvalidError(
                f"Couldn't parse tag {tag_signature!r} "
                f"(type {type_signature!r}, "
                f"offset {int(tag_data_offset):d}, "
                f"size {int(tag_data_size):d}): {exception!r}"
            ) from exception
        self[key] = tag
        return tag

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set the attribute with the given name to the given value.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        if name == "profile":
            object.__setattr__(self, name, value)
        else:
            AODict.__setattr__(self, name, value)

    def get(self, key: str, default: None | Any = None) -> Any:  # noqa: ANN401
        """Return the value of the attribute with the given key.

        Args:
            key (str): The key of the attribute to get.
            default (None | Any, optional): The default value to return if the
                key does not exist.

        Returns:
            Any: The value of the attribute with the given key, or the default
                value if the key does not exist.
        """
        return self[key] if key in self else default  # noqa: SIM401
