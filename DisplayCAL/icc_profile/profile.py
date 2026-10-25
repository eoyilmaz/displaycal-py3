"""Core ICC profile parsing, validation, and manipulation."""

from __future__ import annotations

import binascii
import contextlib
import datetime
import math
import os
import pathlib
import re
import struct
import sys
from hashlib import md5
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Callable,
    ClassVar,
    TextIO,
)
from weakref import WeakValueDictionary

from DisplayCAL import colormath, edid
from DisplayCAL.defaultpaths import ICCPROFILES, ICCPROFILES_HOME

if TYPE_CHECKING:
    import threading
    from typing import BinaryIO, Self, TextIO


from DisplayCAL.icc_profile.codecs import (
    dateTimeNumber,
    dateTimeNumber_tohex,
    hexrepr,
    s15f16_is_equal,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.constants import (
    CIIS,
    CMMS,
    DEBUG,
    MANUFACTURERS,
    PLATFORM,
    PROFILE_CLASS,
    TAGS,
    TECH,
)
from DisplayCAL.icc_profile.structures import (
    AODict,
    DictList,
)
from DisplayCAL.icc_profile.tags import (
    ChromaticAdaptionTag,
    ChromaticityType,
    ColorantTableType,
    CurveType,
    DictType,
    ICCProfileTag,
    LazyLoadTagAODict,
    LUT16Type,
    MakeAndModelType,
    MeasurementType,
    MultiLocalizedUnicodeType,
    NamedColor2Type,
    ParametricCurveType,
    ProfileSequenceDescType,
    Text,
    TextDescriptionType,
    TextType,
    VideoCardGammaFormulaType,
    VideoCardGammaTableType,
    ViewingConditionsType,
    WcsProfilesTagType,
    XYZNumber,
    XYZType,
)


class ICCProfileInvalidError(IOError):
    """Exception raised when an invalid ICC profile is encountered."""


_ICCPROFILE_CACHE = WeakValueDictionary()


class ICCProfile:
    """Return a new ICCProfile object.

    Optionally initialized with a string containing binary profile data or
    a filename, or a file-like object. Also, if the 'load' keyword argument
    is False (default True), only the header will be read initially and
    loading of the tags will be deferred to when they are accessed the
    first time.

    Args:
        profile (None | str | pathlib.Path | bytes | BinaryIO | TextIO, optional):
            The ICC profile data to load. This can be a string or
            pathlib.Path representing a file path, a bytes object
            containing the profile data, or a file-like object.
        load (bool, optional): If True, the profile will be loaded
            immediately. If False, only the header will be read.
        use_cache (bool, optional): If True, the profile will be cached
            to avoid reloading it if it has already been loaded.
    """

    _recent: ClassVar[list] = []

    def __new__(
        cls,
        profile: None | bytes | str | pathlib.Path | BinaryIO | TextIO = None,
        load: bool = True,
        use_cache: bool = False,
    ) -> Self:
        """Look up a cached ICCProfile instance, or allocate a new one.

        This is only responsible for the cache identity check, returning an
        already-loaded instance from `_ICCPROFILE_CACHE` if one matches
        `profile`. All actual profile loading/parsing happens in `__init__`.

        Args:
            profile (None, bytes, str, pathlib.Path, file-like object, optional):
                The ICC profile data to load. This can be a string or
                pathlib.Path representing a file path, a bytes object
                containing the profile data, or a file-like object.
            load (bool, optional): Unused here, kept for signature parity
                with `__init__` since Python calls both with the same args.
            use_cache (bool, optional): If True, resolve a cache key for
                `profile` and return a matching cached instance if found.

        Raises:
            ICCProfileInvalidError: If a path profile is empty.

        Returns:
            ICCProfile: Either a cached instance, or a freshly allocated
            (not yet initialized) instance.
        """
        key = None
        # the content of the profile should be passed as bytes in Python 3.
        if isinstance(profile, (str, pathlib.Path)):
            # Filename
            if not profile:
                raise ICCProfileInvalidError("Empty path given")

            p = pathlib.Path(profile) if isinstance(profile, str) else profile

            if not p.is_file() and not p.is_absolute():
                search_paths = list(set(ICCPROFILES_HOME + ICCPROFILES))
                found_profile = False
                while search_paths and not found_profile:
                    search_path = pathlib.Path(search_paths.pop(0))
                    if not search_path.is_dir():  # only look in to directories
                        continue
                    for entry in search_path.glob(p.name):
                        if not entry.is_file():
                            continue
                        profile = str(entry)
                        # TODO: update this to stay a Path instance after
                        #       migration to pathlib is completed
                        found_profile = True
                        break

            if use_cache:
                stat = os.stat(profile)
                key = (profile, stat.st_dev, stat.st_ino, stat.st_mtime, stat.st_size)
            else:
                key = ()
        elif isinstance(profile, bytes):
            # Binary string
            if use_cache:
                key = md5(profile).hexdigest()  # noqa: S324

        if use_cache:
            chk = _ICCPROFILE_CACHE.get(key)
            if chk:
                return chk

        self = super().__new__(cls)

        if use_cache and key:
            _ICCPROFILE_CACHE[key] = self

            # Make sure most recent three are not garbage collected
            if len(ICCProfile._recent) == 3:
                ICCProfile._recent.pop(0)
            ICCProfile._recent.append(self)

        self._key = key
        self._resolved_profile = profile
        return self

    def __init__(
        self,
        profile: None | bytes | str | pathlib.Path | BinaryIO | TextIO = None,
        load: bool = True,
        use_cache: bool = False,
    ) -> None:
        """Initialize the ICCProfile instance.

        Optionally initialized with a string containing binary profile data or
        a filename, or a file-like object. Also, if the 'load' keyword argument
        is False (default True), only the header will be read initially and
        loading of the tags will be deferred to when they are accessed the
        first time.

        Args:
            profile (None, bytes, str, pathlib.Path, file-like object, optional):
                The ICC profile data to load. This can be a string or
                pathlib.Path representing a file path, a bytes object
                containing the profile data, or a file-like object.
            load (bool, optional): If True, the profile will be loaded
                immediately. If False, only the header will be read.
            use_cache (bool, optional): Unused here (already applied by
                `__new__`), kept for signature parity.

        Raises:
            ICCProfileInvalidError: If the profile data is invalid or
                if the profile cannot be loaded.
        """
        if getattr(self, "_initialized", False):
            # Cache hit: __new__ returned an already-initialized instance.
            return

        profile = self.__dict__.pop("_resolved_profile")

        self.ID = b"\0" * 16
        self._data = b""
        self._file = None
        self._tagoffsets = []  # Original tag offsets
        self._tags = LazyLoadTagAODict(self)
        self.filename = None
        self.is_loaded = False
        self.size = 0
        self._initialized = True

        if isinstance(self._key, tuple):
            # Filename
            profile = open(profile, "rb")  # noqa: SIM115

        if profile is None:
            self.set_defaults()
            return

        if isinstance(profile, bytes):
            # Binary string
            data = profile
            self.is_loaded = True
        else:
            # File object
            self._file = profile
            self.filename = self._file.name
            self._file.seek(0)
            data = self._file.read(128)
            self.close()

        if not data or len(data) < 128:
            raise ICCProfileInvalidError("Not enough data")

        if data[:5] == b"<?xml" or data[:10] == b"<\0?\0x\0m\0l\0":
            # Microsoft WCS profile
            from io import BytesIO

            from defusedxml import ElementTree

            self.filename = None
            self._data = data
            self.load()
            data = self._data
            self._data = b""
            self.set_defaults()
            it = ElementTree.iterparse(BytesIO(data))
            try:
                for _event, elem in it:
                    # Strip all namespaces
                    elem.tag = elem.tag.split("}", 1)[-1]
            except ElementTree.ParseError as e:
                raise ICCProfileInvalidError("Invalid WCS profile") from e
            desc = it.root.find(b"Description")
            if desc is not None:
                desc = desc.find(b"Text")
                if desc is not None:
                    self.setDescription(str(desc.text, "UTF-8"))
            author = it.root.find(b"Author")
            if author is not None:
                author = author.find(b"Text")
                if author is not None:
                    self.setCopyright(str(author.text, "UTF-8"))
            device = it.root.find(b"RGBVirtualDevice")
            if device is not None:
                measurement_data = device.find(b"MeasurementData")
                if measurement_data is not None:
                    for color in (b"White", b"Red", b"Green", b"Blue", b"Black"):
                        prim = measurement_data.find(color + b"Primary")
                        if prim is None:
                            continue
                        XYZ = []  # noqa: N806
                        for component in b"XYZ":
                            try:
                                XYZ.append(float(prim.get(component)) / 100.0)
                            except (TypeError, ValueError) as e:
                                raise ICCProfileInvalidError(
                                    "Invalid WCS profile"
                                ) from e
                        if color == b"White":
                            tag_name = "wtpt"
                        elif color == b"Black":
                            tag_name = "bkpt"
                        else:
                            XYZ = colormath.adapt(  # noqa: N806
                                *XYZ,
                                whitepoint_source=list(self.tags.wtpt.values()),
                            )
                            tag_name = color[0].lower().decode() + "XYZ"
                        tag = self.tags[tag_name] = XYZType(profile=self)
                        tag.X, tag.Y, tag.Z = XYZ
                    gamma = measurement_data.find(b"GammaOffsetGainLinearGain")
                    if gamma is None:
                        gamma = measurement_data.find(b"GammaOffsetGain")
                    if gamma is not None:
                        params = {
                            "Gamma": 1,
                            "Offset": 0,
                            "Gain": 1,
                            "LinearGain": 1,
                            "TransitionPoint": -1,
                        }
                        for att in list(params.keys()):
                            try:
                                params[att] = float(gamma.get(att))
                            except (TypeError, ValueError) as e:
                                if (
                                    att not in ("LinearGain", "TransitionPoint")
                                    or gamma.tag != "GammaOffsetGain"
                                ):
                                    raise ICCProfileInvalidError(
                                        "Invalid WCS profile"
                                    ) from e

                        def power(a: float) -> float:
                            """Calculate power value based on gamma and parameters.

                            Args:
                                a (float): The input value to calculate the power for.
                            """
                            if a <= params["TransitionPoint"]:
                                v = a / params["LinearGain"]
                            else:
                                v = math.pow(
                                    (a + params["Offset"]) * params["Gain"],
                                    params["Gamma"],
                                )
                            return v

                    else:
                        gamma = measurement_data.find("Gamma")
                        if gamma is not None:
                            try:
                                power = float(gamma.get("value"))
                            except (TypeError, ValueError) as e:
                                raise ICCProfileInvalidError(
                                    "Invalid WCS profile"
                                ) from e
                    if gamma is not None:
                        self.set_trc_tags(True, power)
            if it.root.tag == "ColorDeviceModel":
                ms00 = WcsProfilesTagType(b"", "MS00", self)
                ms00["ColorDeviceModel"] = it.root
                vcgt = ms00.get_vcgt()
                if vcgt:
                    self.tags["vcgt"] = vcgt
            self.size = len(self.data)
            return

        if data[36:40] != b"acsp":
            raise ICCProfileInvalidError(
                "Profile signature mismatch - expected 'acsp', found '"
                + data[36:40].decode("utf-8")
                + "'"
            )

        # ICC profile
        header = data[:128]
        self.size = uInt32Number(header[0:4])
        self.preferredCMM = header[4:8]
        minorrev_bugfixrev = binascii.hexlify(header[8:12][1:2])
        self.version = float(
            "{}.{}".format(
                header[8:12][0],
                str(int(b"0x0" + minorrev_bugfixrev[0:1], 16))
                + str(int(b"0x0" + minorrev_bugfixrev[1:2], 16)),
            )
        )
        self.profileClass = header[12:16]
        self.colorSpace = header[16:20].strip()
        self.connectionColorSpace = header[20:24].strip()
        try:
            self.dateTime = dateTimeNumber(header[24:36])
        except ValueError as e:
            raise ICCProfileInvalidError("Profile creation date/time invalid") from e
        self.platform = header[40:44]
        flags = uInt32Number(header[44:48])
        self.embedded = flags & 1 != 0
        self.independent = flags & 2 == 0
        deviceAttributes = uInt32Number(header[56:60])  # noqa: N806

        self.device = {
            "manufacturer": header[48:52],
            "model": header[52:56],
            "attributes": {
                "reflective": deviceAttributes & 1 == 0,
                "glossy": deviceAttributes & 2 == 0,
                "positive": deviceAttributes & 4 == 0,
                "color": deviceAttributes & 8 == 0,
            },
        }
        self.intent = uInt32Number(header[64:68])
        self.illuminant = XYZNumber(header[68:80])
        self.creator = header[80:84]
        if header[84:100] != b"\0" * 16:
            self.ID = header[84:100]

        self._data = data[: self.size]

        if load:
            _ = self.tags

    def set_defaults(self) -> None:
        """Set default values for the ICC profile."""
        if hasattr(self, "version"):
            return  # Already initialized
        # Default to RGB display device profile
        self.preferredCMM = b"argl"
        self.version = 2.4
        self.profileClass = b"mntr"
        self.colorSpace = b"RGB"
        self.connectionColorSpace = b"XYZ"
        self.dateTime = datetime.datetime.now()
        if sys.platform == "win32":
            platform_id = b"MSFT"  # Microsoft
        elif sys.platform == "darwin":
            platform_id = b"APPL"  # Apple
        else:
            platform_id = b"*nix"
        self.platform = platform_id
        self.embedded = False
        self.independent = True
        self.device = {
            "manufacturer": b"",
            "model": b"",
            "attributes": {
                "reflective": True,
                "glossy": True,
                "positive": True,
                "color": True,
            },
        }
        self.intent = 0
        self.illuminant = XYZNumber(b"\0\0\xf6\xd6\0\x01\0\0\0\0\xd3-")  # D50
        self.creator = b"DCAL"  # DisplayCAL

    def __len__(self) -> int:
        """Return the number of tags.

        Can also be used in boolean comparisons (profiles with no tags
        evaluate to false).

        Returns:
            int: The number of tags in the profile.
        """
        return len(self.tags)

    @property
    def data(self) -> bytes:
        """Get raw binary profile data.

        This will re-assemble the various profile parts (header, tag table and data)
        on-the-fly.

        Returns:
            bytes: The raw binary profile data.
        """
        # Assemble tag table and tag data
        tagCount = len(self.tags)  # noqa: N806
        tagTable = {}  # noqa: N806
        tagTableSize = tagCount * 12  # noqa: N806
        tagsData = []  # noqa: N806
        tagsDataOffset = []  # noqa: N806
        tagDataOffset = 128 + 4 + tagTableSize  # noqa: N806
        tags = []
        # Order of tag table and actual tag data may be different.
        # Keep order of tags according to original offsets (if any).
        for _oOffset, tagSignature in sorted(self._tagoffsets):  # noqa: N806
            if tagSignature in self.tags:
                tags.append(tagSignature)

        # Keep tag table order
        for tagSignature in self.tags:  # noqa: N806
            tagTable[tagSignature] = tagSignature.encode()
            if tagSignature not in tags:
                tags.append(tagSignature)

        for tagSignature in tags:  # noqa: N806
            tag = AODict.__getitem__(self.tags, tagSignature)
            if isinstance(tag, ICCProfileTag):
                tagData = self.tags[tagSignature].tagData  # noqa: N806
            else:
                tagData = tag[3]  # noqa: N806
            tagDataSize = len(tagData)  # noqa: N806
            # Pad all data with binary zeros, so it lies on 4-byte boundaries
            padding = math.ceil(tagDataSize / 4.0) * 4 - tagDataSize
            tagData += b"\0" * padding  # noqa: N806
            if (
                tagDataOffset,
                tagSignature,
            ) not in self._tagoffsets and tagData in tagsData:
                tagTable[tagSignature] += uInt32Number_tohex(
                    tagsDataOffset[tagsData.index(tagData)]
                )
            else:
                tagTable[tagSignature] += uInt32Number_tohex(tagDataOffset)
                tagsData.append(tagData)
                tagsDataOffset.append(tagDataOffset)
                tagDataOffset += tagDataSize + padding  # noqa: N806
            tagTable[tagSignature] += uInt32Number_tohex(tagDataSize)
        tagsData = b"".join(tagsData)  # noqa: N806
        header = self.header(tagTableSize, len(tagsData))
        return b"".join(
            [
                header,
                uInt32Number_tohex(tagCount),
                b"".join(list(tagTable.values())),
                tagsData,
            ]
        )

    def header(self, tagTableSize: int, tagDataSize: int) -> bytes:  # noqa: N803
        """Profile Header.

        Args:
            tagTableSize (int): Size of the tag table in bytes.
            tagDataSize (int): Size of the tag data in bytes.

        Returns:
            bytes: The profile header as a byte string.
        """
        # Profile size: 128 bytes header + 4 bytes tag count + tag table + data
        header = [
            uInt32Number_tohex(128 + 4 + tagTableSize + tagDataSize),
            self.preferredCMM[:4].ljust(4, b" ") if self.preferredCMM else b"\0" * 4,
            # Next three lines are ICC version
            chr(int(str(self.version).split(".")[0])).encode(),
            binascii.unhexlify((f"{self.version:.2f}").split(".")[1]),
            b"\0" * 2,
            self.profileClass[:4].ljust(4, b" "),
            self.colorSpace[:4].ljust(4, b" "),
            self.connectionColorSpace[:4].ljust(4, b" "),
            dateTimeNumber_tohex(self.dateTime),
            b"acsp",
            self.platform[:4].ljust(4, b" ") if self.platform else b"\0" * 4,
        ]

        flags = 0
        if self.embedded:
            flags += 1
        if not self.independent:
            flags += 2

        header.extend(
            [
                uInt32Number_tohex(flags),
                (
                    self.device["manufacturer"][:4].rjust(4, b"\0")
                    if self.device["manufacturer"]
                    else b"\0" * 4
                ),
                (
                    self.device["model"][:4].rjust(4, b"\0")
                    if self.device["model"]
                    else b"\0" * 4
                ),
            ]
        )
        deviceAttributes = 0  # noqa: N806
        for name, bit in {
            "reflective": 1,
            "glossy": 2,
            "positive": 4,
            "color": 8,
        }.items():
            if not self.device["attributes"][name]:
                deviceAttributes += bit  # noqa: N806
        if sys.platform == "darwin" and self.version < 4:
            # Dont't include ID under Mac OS X unless v4 profile
            # to stop pedantic ColorSync utility from complaining
            # about header padding not being null
            id_ = b""
        else:
            id_ = self.ID[:16]

        if isinstance(self._data, str):
            self._data = self._data.encode()

        header.extend(
            [
                uInt32Number_tohex(deviceAttributes) + b"\0" * 4,
                uInt32Number_tohex(self.intent),
                self.illuminant.tohex(),
                self.creator[:4].ljust(4, b" ") if self.creator else b"\0" * 4,
                id_.ljust(16, b"\0"),
                self._data[100:128] if len(self._data[100:128]) == 28 else b"\0" * 28,
            ]
        )

        return b"".join(header)

    @property
    def tags(self) -> LazyLoadTagAODict:
        """Profile Tag Table.

        Raises:
            ICCProfileInvalidError: If the tag table is truncated or
                if a tag signature is already encountered.

        Returns:
            LazyLoadTagAODict: A dictionary-like object containing the
                profile's tags.
        """
        if self._tags:
            return self._tags

        self.load()
        if not self._data or len(self._data) <= 131:
            return self._tags

        # tag table and tagged element data
        tagCount = uInt32Number(self._data[128:132])  # noqa: N806
        if DEBUG:
            print("tagCount:", tagCount)

        tagTable = self._data[132 : 132 + tagCount * 12]  # noqa: N806
        self._tagoffsets = []
        discard_len = 0
        tags = {}
        while tagTable:
            tag = tagTable[:12]
            if len(tag) < 12:
                raise ICCProfileInvalidError("Tag table is truncated")

            tagSignature = tag[:4].decode()  # noqa: N806
            if DEBUG:
                print("tagSignature:", tagSignature)

            tagDataOffset = uInt32Number(tag[4:8])  # noqa: N806
            self._tagoffsets.append((tagDataOffset, tagSignature))
            if DEBUG:
                print("    tagDataOffset:", tagDataOffset)

            tagDataSize = uInt32Number(tag[8:12])  # noqa: N806
            if DEBUG:
                print("    tagDataSize:", tagDataSize)

            if tagSignature in self._tags:
                print(
                    f"Error (non-critical): Tag '{tagSignature}' "
                    "already encountered. Skipping..."
                )
            else:
                if (tagDataOffset, tagDataSize) in tags:
                    if DEBUG:
                        print("    tagDataOffset and tagDataSize indicate shared tag")
                else:
                    start = tagDataOffset - discard_len
                    if DEBUG:
                        print("    tagData start:", start)

                    end = tagDataOffset - discard_len + tagDataSize
                    if DEBUG:
                        print("    tagData end:", end)

                    tagData = self._data[start:end]  # noqa: N806
                    if len(tagData) < tagDataSize:
                        print(
                            f"Warning: Tag data for tag {tagSignature!r} "
                            f"is truncated (offset {int(tagDataOffset):d}, "
                            f"expected size {int(tagDataSize):d}, "
                            f"actual size {len(tagData):d})"
                        )
                        tagDataSize = len(tagData)  # noqa: N806
                    typeSignature = tagData[:4]  # noqa: N806
                    if len(typeSignature) < 4:
                        print(
                            "Warning: Tag type signature for tag "
                            f"{tagSignature!r} is truncated "
                            f"(offset {int(tagDataOffset):d}, "
                            f"size {int(tagDataSize):d})"
                        )
                        typeSignature = typeSignature.ljust(4, b" ")  # noqa: N806
                    if DEBUG:
                        print("    typeSignature:", typeSignature)
                    tags[(tagDataOffset, tagDataSize)] = (
                        typeSignature,
                        tagDataOffset,
                        tagDataSize,
                        tagData,
                    )
                self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)]
            tagTable = tagTable[12:]  # noqa: N806

        self._data = self._data[:128]
        return self._tags

    def calculate_id(self, set_id: bool = True) -> bytes:
        """Calculates, sets, and returns the profile's ID (checksum).

        Calling this function always recalculates the checksum on-the-fly,
        in contrast to just accessing the ID property.

        The entire profile, based on the size field in the header, is used
        to calculate the ID after the values in the Profile Flags field
        (bytes 44 to 47), Rendering Intent field (bytes 64 to 67) and
        Profile ID field (bytes 84 to 99) in the profile header have been
        temporarily replaced with zeros.

        Args:
            set_id (bool, optional): If True, the calculated ID will be set as
                the profile's ID. If False, the ID will not be set, but still
                returned. Defaults to True.

        Returns:
            bytes: The calculated ID as a 16-byte binary string.
        """
        data = self.data
        data = (
            data[:44]
            + b"\0\0\0\0"
            + data[48:64]
            + b"\0\0\0\0"
            + data[68:84]
            + b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
            + data[100:]
        )
        id_ = md5(data).digest()  # noqa: S324
        if set_id:
            if id_ != self.ID:
                # No longer reflects original profile
                self._delfromcache()
            self.ID = id_
        return id_

    def close(self) -> None:
        """Close the associated file object (if any)."""
        if self._file and not self._file.closed:
            self._file.close()

    def convert_iccv4_tags_to_iccv2(
        self,
        version: float = 2.4,
        undo_wtpt_chad: bool = False,
    ) -> bool:
        """Convert ICCv4 parametric curve tags to ICCv2-compatible curve tags.

        If desired version after conversion is < 2.4 and undo_wtpt_chad is True,
        also set whitepoint to illuinant relative values, and remove any
        chromatic adaptation tag.

        If ICC profile version is < 4 or no [rgb]TRC tags or LUT16Type tags,
        return False.
        Otherwise, convert curve tags and return True.

        Args:
            version (float, optional): The desired ICC profile version after
                conversion. Defaults to 2.4.
            undo_wtpt_chad (bool, optional): If True, set whitepoint to
                illuminant relative values and remove chromatic adaptation tag
                if present. Defaults to False.

        Returns:
            bool: True if conversion was successful, False if the profile
        """
        if self.version < 4:
            return False
        # Fail if any LUT tag is not LUT16Type as we currently
        # have not implemented conversion (which may not even
        # be possible, depending on LUT contents)
        has_lut_tags = False
        for direction in ("A2B", "B2A"):
            for tableno in range(3):
                tag = self.tags.get(f"{direction}{tableno}")
                if tag:
                    if isinstance(tag, LUT16Type):
                        has_lut_tags = True
                    else:
                        return False
        if self.has_trc_tags():
            for channel in "rgb":
                tag = self.tags[channel + "TRC"]
                if isinstance(tag, ParametricCurveType):
                    # Convert to CurveType
                    self.tags[channel + "TRC"] = tag.get_trc()
        elif not has_lut_tags:
            return False
        # Set filename to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.filename = None
        self._delfromcache()
        if version < 2.4 and undo_wtpt_chad:
            # Set whitepoint tag to illuminant relative and remove chromatic
            # adaptation tag afterwards(!)
            self.tags.wtpt = self.tags.wtpt.ir
            if "chad" in self.tags:
                del self.tags["chad"]
        # Get all multiLocalizedUnicodeType tags
        mluc = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if isinstance(tag, MultiLocalizedUnicodeType):
                mluc[tagname] = str(tag)
        # Set profile version
        self.version = version
        # Convert to textDescriptionType/textType (after setting version to 2.x)
        for tagname in mluc:
            unistr = mluc[tagname]
            if tagname == "cprt":
                self.setCopyright(unistr)
            else:
                self.set_localizable_desc(tagname, unistr)
        return True

    def convert_iccv2_tags_to_iccv4(self) -> bool:
        """Convert ICCv2 text description tags to ICCv4 multi-localized unicode.

        Also sets whitepoint to D50, and stores illuminant-relative to D50
        matrix as chromatic adaptation tag.

        If ICC profile version is >= 4, return False.
        Otherwise, convert and return True.

        After conversion, the profile version is 4.3

        Returns:
            bool: True if conversion was successful, False if the profile
                version is already >= 4.
        """
        if self.version >= 4:
            return False
        # Set filename to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.filename = None
        self._delfromcache()
        wtpt = list(self.tags.wtpt.ir.values())
        # Set whitepoint tag to D50
        self.tags.wtpt = self.tags.wtpt.pcs
        if "chad" not in self.tags:
            # Set chromatic adaptation matrix
            self.tags["chad"] = ChromaticAdaptionTag()
            wpam = colormath.wp_adaption_matrix(
                wtpt, cat=self.tags.get("arts", "Bradford")
            )
            self.tags["chad"].update(wpam)
        # Get all textDescriptionType tags
        text = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if tagname == "cprt" or isinstance(tag, TextDescriptionType):
                text[tagname] = str(tag)
        # Set profile version to 4.3
        self.version = 4.3
        # Convert to multiLocalizedUnicodeType (after setting version to 4.x)
        for tagname in text:
            unistr = text[tagname]
            self.set_localizable_text(tagname, unistr)
        return True

    @staticmethod
    def from_named_rgb_space(
        rgb_space_name: str,
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        """Create an ICC Profile from a named RGB space and return it.

        Args:
            rgb_space_name (str): The name of the RGB space, e.g. "sRGB",
                "AdobeRGB".
            iccv4 (bool): Whether to create an ICC v4 profile.
            cat (str): Chromatic adaptation transform to use.
            profile_class (bytes): The profile class, e.g. b'mntr' for monitor
                profiles.

        Returns:
            ICCProfile: The created ICC profile.
        """
        rgb_space = colormath.get_rgb_space(rgb_space_name)
        return ICCProfile.from_rgb_space(
            rgb_space, rgb_space_name, iccv4, cat, profile_class
        )

    @staticmethod
    def from_rgb_space(
        rgb_space: tuple[
            tuple[float, float, float],
            tuple[float, float, float],
            tuple[float, float, float],
        ],
        description: str,
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        """Create an ICC Profile from RGB space and return it.

        Args:
            rgb_space (None | str | list | tuple): The RGB space to use for
                conversion. Defaults to sRGB if not set. If a string is given,
                it must be a valid RGB space name. If a list or tuple is given,
                it must be in the format (gamma, whitepoint, red, green, blue).
                The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
                coordinates, or a color temperature in degrees K (float or
                int). The gamma should be a float. The RGB primaries red,
                green, blue should be lists or tuples of xyY coordinates (only
                x and y will be used, so Y can be zero or None).
            description (str): A description for the profile.
            iccv4 (bool): Whether to create an ICC v4 profile.
            cat (str): Chromatic adaptation transform to use.
            profile_class (bytes): The profile class, e.g. b'mntr' for monitor
                profiles.

        Returns:
            ICCProfile: The created ICC profile.
        """
        rx, ry = rgb_space[2:][0][:2]
        gx, gy = rgb_space[2:][1][:2]
        bx, by = rgb_space[2:][2][:2]
        wx, wy = colormath.XYZ2xyY(*rgb_space[1])[:2]
        return ICCProfile.from_chromaticities(
            rx,
            ry,
            gx,
            gy,
            bx,
            by,
            wx,
            wy,
            rgb_space[0],
            description,
            "No copyright",
            iccv4=iccv4,
            cat=cat,
            profile_class=profile_class,
        )

    @staticmethod
    def from_edid(
        edid: dict,
        iccv4: bool = False,
        cat: str = "Bradford",
    ) -> ICCProfile:
        """Create an ICC Profile from EDID data and return it.

        You may override the gamma from EDID by setting it to a list of curve
        values.

        Args:
            edid (dict): EDID data as a dictionary.
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
            cat (str, optional): Chromatic adaptation transform to use.

        Returns:
            ICCProfile: The created ICC profile.
        """
        description = edid.get(
            "monitor_name", edid.get("ascii", str(edid["product_id"] or edid["hash"]))
        )
        manufacturer = edid.get("manufacturer", b"")
        manufacturer_id = edid["edid"][8:10]
        model_name = description
        model_id = edid["edid"][10:12]
        copyright_str = "Created from EDID"
        # Get chromaticities of primaries0
        xy = {}
        for color in ("red", "green", "blue", "white"):
            x, y = edid.get(color + "_x", 0.0), edid.get(color + "_y", 0.0)
            xy[color[0] + "x"] = x
            xy[color[0] + "y"] = y
        gamma = edid.get("gamma", 2.2)
        profile = ICCProfile.from_chromaticities(
            xy["rx"],
            xy["ry"],
            xy["gx"],
            xy["gy"],
            xy["bx"],
            xy["by"],
            xy["wx"],
            xy["wy"],
            gamma,
            description,
            copyright_str,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
        )
        profile.set_edid_metadata(edid)
        spec_prefixes = "DATA_,OPENICC_"
        prefix = profile.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        profile.tags.meta["prefix"] = ",".join(prefixes)
        profile.tags.meta["OPENICC_automatic_generated"] = "1"
        profile.tags.meta["DATA_source"] = "edid"
        profile.calculate_id()
        return profile

    @staticmethod
    def from_chromaticities(
        rx: float,
        ry: float,
        gx: float,
        gy: float,
        bx: float,
        by: float,
        wx: float,
        wy: float,
        gamma: float | list,
        description: str,
        copyright_: str,
        manufacturer: None | str = None,
        model_name: None | str = None,
        manufacturer_id: bytes = b"\0\0",
        model_id: bytes = b"\0\0",
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        r"""Create an ICC Profile from chromaticities and return it.

        Args:
            rx (float): Red primary x chromaticity.
            ry (float): Red primary y chromaticity.
            gx (float): Green primary x chromaticity.
            gy (float): Green primary y chromaticity.
            bx (float): Blue primary x chromaticity.
            by (float): Blue primary y chromaticity.
            wx (float): White point x chromaticity.
            wy (float): White point y chromaticity.
            gamma (float | list): Gamma value or list of curve values.
            description (str): A description for the profile.
            copyright_ (str): Copyright information for the profile.
            manufacturer (None | str, optional): Manufacturer name. Defaults to
                None.
            model_name (None | str, optional): Model name. Defaults to None.
            manufacturer_id (bytes, optional): Manufacturer ID as a 4-byte
                string. Defaults to b"\0\0".
            model_id (bytes, optional): Model ID as a 4-byte string. Defaults
                to b"\0\0".
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
                Defaults to False.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".
            profile_class (bytes, optional): The profile class, e.g. b'mntr'
                for monitor profiles. Defaults to b'mntr'.

        Returns:
            ICCProfile: The created ICC profile.
        """
        wXYZ = colormath.xyY2XYZ(wx, wy, 1.0)  # noqa: N806
        # Calculate RGB to XYZ matrix from chromaticities and white
        mtx = colormath.rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, wXYZ)
        rgb = {"r": (1.0, 0.0, 0.0), "g": (0.0, 1.0, 0.0), "b": (0.0, 0.0, 1.0)}
        XYZ = {}  # noqa: N806
        for color in "rgb":
            # Calculate XYZ for primaries
            XYZ[color] = mtx * rgb[color]

        return ICCProfile.from_XYZ(
            XYZ["r"],
            XYZ["g"],
            XYZ["b"],
            wXYZ,
            gamma,
            description,
            copyright_,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
            profile_class,
        )

    @staticmethod
    def from_XYZ(  # noqa: N802
        rXYZ: tuple[float, float, float],  # noqa: N803
        gXYZ: tuple[float, float, float],  # noqa: N803
        bXYZ: tuple[float, float, float],  # noqa: N803
        wXYZ: tuple[float, float, float],  # noqa: N803
        gamma: float | list,
        description: str,
        copyright_: str,
        manufacturer: None | str = None,
        model_name: None | str = None,
        manufacturer_id: bytes = b"\0\0",
        model_id: bytes = b"\0\0",
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        r"""Create an ICC Profile from XYZ values and return it.

        Args:
            rXYZ (tuple[float, float, float]): Red primary in absolute XYZ.
            gXYZ (tuple[float, float, float]): Green primary in absolute XYZ.
            bXYZ (tuple[float, float, float]): Blue primary in absolute XYZ.
            wXYZ (tuple[float, float, float]): White point in absolute XYZ.
            gamma (float | list): Gamma value or list of curve values.
            description (str): A description for the profile.
            copyright_ (str): Copyright information for the profile.
            manufacturer (None | str, optional): Manufacturer name. Defaults to
                None.
            model_name (None | str, optional): Model name. Defaults to None.
            manufacturer_id (bytes, optional): Manufacturer ID as a 4-byte
                string. Defaults to b"\0\0".
            model_id (bytes, optional): Model ID as a 4-byte string. Defaults
                to b"\0\0".
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
                Defaults to False.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".
            profile_class (bytes, optional): The profile class, e.g. b'mntr'
                for monitor profiles. Defaults to b'mntr'.

        Returns:
            ICCProfile: The created ICC profile.
        """
        profile = ICCProfile()
        profile.profileClass = profile_class
        D50 = colormath.get_whitepoint("D50")  # noqa: N806
        if iccv4:
            profile.version = 4.3
        elif not s15f16_is_equal(wXYZ, D50) and (
            profile.profileClass not in (b"mntr", b"prtr")
            or colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            profile.version = 2.2  # Match ArgyllCMS
        profile.setDescription(description)
        profile.setCopyright(copyright_)
        if manufacturer:
            profile.setDeviceManufacturerDescription(manufacturer)
        if model_name:
            profile.setDeviceModelDescription(model_name)

        profile.device["manufacturer"] = (
            b"\0\0" + manufacturer_id[1:] + manufacturer_id[:1]
        )
        profile.device["model"] = b"\0\0" + model_id[1:] + model_id[:1]
        # Add Apple-specific 'mmod' tag (TODO: need full spec)
        if manufacturer_id != b"\0\0" or model_id != b"\0\0":
            mmod = (
                b"mmod"
                + (b"\x00" * 6)
                + manufacturer_id
                + (b"\x00" * 2)
                + model_id[1:]
                + model_id[:1]
                + (b"\x00" * 4)
                + (b"\x00" * 20)
            )
            profile.tags.mmod = ICCProfileTag(mmod, "mmod")
        profile.set_wtpt(wXYZ, cat)
        profile.tags.chrm = ChromaticityType()
        profile.tags.chrm.type = 0

        for color_value, color_name in ((rXYZ, "r"), (gXYZ, "g"), (bXYZ, "b")):
            X, Y, Z = color_value  # noqa: N806
            # Get chromaticity of primary
            x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
            profile.tags.chrm.channels.append((x, y))
            # Write XYZ and TRC tags (don't forget to adapt to D50)
            tagname = f"{color_name}XYZ"
            profile.tags[tagname] = XYZType(profile=profile)
            (
                profile.tags[tagname].X,
                profile.tags[tagname].Y,
                profile.tags[tagname].Z,
            ) = colormath.adapt(X, Y, Z, wXYZ, D50, cat)
            tagname = f"{color_name}TRC"
            profile.tags[tagname] = CurveType(profile=profile)
            if isinstance(gamma, (list, tuple)):
                profile.tags[tagname].extend(gamma)
            else:
                profile.tags[tagname].set_trc(gamma, 1)
        profile.calculate_id()
        return profile

    def set_wtpt(self, wXYZ: tuple[float, float, float], cat: str = "Bradford") -> None:  # noqa: N803
        """Set whitepoint, 'chad' tag and add ArgyllCMS 'arts' tag.

        if >= v2.4 profile or CAT is not Bradford and wtpt is not D50.

        Args:
            wXYZ (tuple[float, float, float]): White point in absolute XYZ, Y
                range 0.0..1.0.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to 'Bradford'.
        """
        self.tags.wtpt = XYZType(profile=self)
        # Compatibility: ArgyllCMS will only read 'chad' if display or
        # output profile
        if self.profileClass in (b"mntr", b"prtr") and (
            self.version >= 2.4
            or not colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            # Set wtpt to D50 and store actual white -> D50 transform in chad
            # if creating ICCv4 profile or CAT is not default Bradford
            D50 = colormath.get_whitepoint("D50")  # noqa: N806
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = D50
            if not s15f16_is_equal(wXYZ, D50):
                # Only create chad if actual white is not D50
                self.tags.chad = ChromaticAdaptionTag()
                matrix = colormath.wp_adaption_matrix(wXYZ, D50, cat)
                self.tags.chad.update(matrix)
        else:
            # Store actual white in wtpt
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = wXYZ
        self.tags.arts = ChromaticAdaptionTag()
        self.tags.arts.update(colormath.get_cat_matrix(cat))

    def has_trc_tags(self) -> bool:
        """Return whether the profile has [rgb]TRC tags.

        Returns:
            bool: True if the profile has [rgb]TRC tags, False otherwise.
        """
        return False not in [channel + "TRC" in self.tags for channel in "rgb"]

    def set_blackpoint(self, XYZbp: tuple[float, float, float]) -> None:  # noqa: N803
        """Set the black point tag to the given XYZ value.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0.0..1.0.
        """
        if "chad" not in self.tags:
            cat = self.guess_cat() or "Bradford"
            XYZbp = colormath.adapt(  # noqa: N806
                *XYZbp, whitepoint_destination=list(self.tags.wtpt.ir.values()), cat=cat
            )
        self.tags.bkpt = XYZType(tagSignature="bkpt", profile=self)
        self.tags.bkpt.X, self.tags.bkpt.Y, self.tags.bkpt.Z = XYZbp

    def apply_black_offset(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        power: float = 40.0,
        include_A2B: bool = True,  # noqa: N803
        set_blackpoint: bool = True,
        logfile: None | TextIO = None,
        thread_abort: None | threading.Event = None,
        abortmessage: str = "Aborted",
        include_trc: bool = True,
    ) -> None:
        """Apply black point blending to the profile.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0.0..1.0.
            power (float, optional): Power of black point blending. Defaults to
                40.0.
            include_A2B (bool, optional): Whether to apply black point blending
                to A2B tables. Defaults to True.
            set_blackpoint (bool, optional): Whether to set the black point
                tag. Defaults to True.
            logfile (None | TextIO, optional): File-like object to write the
                log messages to. Defaults to None.
            thread_abort (None | threading.Event, optional): Event to signal
                thread abort. Defaults to None.
            abortmessage (str, optional): Message to display when thread is
                aborted. Defaults to "Aborted".
            include_trc (bool, optional): Whether to apply black point blending
                to TRC tags. Defaults to True.
        """
        # Apply only the black point blending portion of BT.1886 mapping
        if include_A2B:
            tables = []
            for i in range(3):
                a2b = self.tags.get(f"A2B{i}")
                if isinstance(a2b, LUT16Type) and a2b not in tables:
                    a2b.apply_black_offset(XYZbp, logfile, thread_abort, abortmessage)
                    tables.append(a2b)
        if set_blackpoint:
            self.set_blackpoint(XYZbp)
        if not self.tags.get("rTRC") or not include_trc:
            return
        rXYZ = list(self.tags.rXYZ.values())  # noqa: N806
        gXYZ = list(self.tags.gXYZ.values())  # noqa: N806
        bXYZ = list(self.tags.bXYZ.values())  # noqa: N806
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        imtx = mtx.inverted()
        for channel in "rgb":
            tag = CurveType(profile=self)
            if len(self.tags[f"{channel}TRC"]) == 1:
                gamma = self.tags[f"{channel}TRC"].get_gamma()
                tag.set_trc(gamma, 1024)
            else:
                tag.extend(self.tags[channel + "TRC"])
            self.tags[channel + "TRC"] = tag
        rgbbp_in = [self.tags[f"{channel}TRC"][0] / 65535.0 for channel in "rgb"]
        bp_in = mtx * rgbbp_in
        if tuple(bp_in) == tuple(XYZbp):
            return
        size = len(self.tags.rTRC)
        for i in range(size):
            rgb = [self.tags[f"{channel}TRC"][i] / 65535.0 for channel in "rgb"]
            X, Y, Z = mtx * rgb  # noqa: N806
            XYZ = colormath.blend_blackpoint(X, Y, Z, bp_in, XYZbp, power=power)  # noqa: N806
            rgb = imtx * XYZ
            for j, channel in enumerate("rgb"):
                self.tags[f"{channel}TRC"][i] = min(max(rgb[j], 0), 1) * 65535

    def set_bt1886_trc(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        outoffset: float = 0.0,
        gamma: float = 2.4,
        gamma_type: str = "B",
        size: None | int = None,
    ) -> None:
        """Set the response to the BT.1886 function.

        Args:
            XYZbp (tuple): Black point in absolute XYZ, Y range 0.0..1.0.
            outoffset (float): Output offset (default 0.0).
            gamma (float): Effective gamma (default 2.4).
            gamma_type (str, optional): Type of gamma to use, either 'b' for
                BT.1886 or 'g' for gamma (default 'B').
            size (None | int): Number of steps. Recommended >= 1024.
        """
        if gamma_type in ("b", "g"):
            # Get technical gamma needed to achieve effective gamma
            gamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
        rXYZ = list(self.tags.rXYZ.values())  # noqa: N806
        gXYZ = list(self.tags.gXYZ.values())  # noqa: N806
        bXYZ = list(self.tags.bXYZ.values())  # noqa: N806
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
        values = {}
        for _i, channel in enumerate(("r", "g", "b")):
            self.tags[channel + "TRC"] = CurveType(profile=self)
            self.tags[channel + "TRC"].set_trc(-709, size)
            for j, v in enumerate(self.tags[channel + "TRC"]):
                if not values.get(j):
                    values[j] = []
                values[j].append(v / 65535.0)
        for i in values:
            r, g, b = values[i]
            X, Y, Z = mtx * (r, g, b)  # noqa: N806
            values[i] = bt1886.apply(X, Y, Z)
        for i in values:
            XYZ = values[i]  # noqa: N806
            rgb = mtx.inverted() * XYZ
            for j, channel in enumerate(("r", "g", "b")):
                self.tags[channel + "TRC"][i] = max(min(rgb[j] * 65535, 65535), 0)
        self.set_blackpoint(XYZbp)

    def set_dicom_trc(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        white_cdm2: float = 100,
        size: int = 1024,
    ) -> None:
        """Set the response to the DICOM Grayscale Standard Display Function.

        This response is special in that it depends on the actual black
        and white level of the display.

        XYZbp (tuple[float, float, float]: Black point in absolute XYZ, Y range
            0.05..white_cdm2.
        white_cdm2 (float, optional): White level in candelas per square
            meter, defaults to 100.
        size (int, optional): Number of steps. Recommended >= 1024.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_dicom_trc(XYZbp[1], white_cdm2, size)
        self.apply_black_offset(
            [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 40.0)
        )

    def set_hlg_trc(
        self,
        XYZbp: tuple[float, float, float] = (0, 0, 0),  # noqa: N803
        white_cdm2: float = 100,
        system_gamma: float = 1.2,
        ambient_cdm2: float = 5,
        maxsignal: float = 1.0,
        size: int = 1024,
        blend_blackpoint: bool = True,
    ) -> None:
        """Set the response to the Hybrid Log-Gamma (HLG) function.

        This response is special in that it depends on the actual black and
        white level of the display, system gamma and ambient.

        XYZbp (tuple[float, float, float], optional): Black point in absolute
            XYZ, Y range 0..white_cdm2.
        white_cdm2 (float, optional): White level in candelas per square
            meter, defaults to 100.
        system_gamma (float, optional): System gamma, defaults to 1.2.
        ambient_cdm2 (float, optional): Ambient light level in candelas per
            square meter, defaults to 5.
        maxsignal (float, optional): Set clipping point. Defaults to 1.0.
        size (int, optional): Number of steps. Recommended >= 1024.
        blend_blackpoint (bool, optional): If True, applies black point
            blending. Defaults to True.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_hlg_trc(
                XYZbp[1], white_cdm2, system_gamma, ambient_cdm2, maxsignal, size
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_smpte2084_trc(
        self,
        XYZbp: tuple[float, float, float] = (0, 0, 0),  # noqa: N803
        white_cdm2: float = 100,
        master_black_cdm2: float = 0,
        master_white_cdm2: float = 10000,
        use_alternate_master_white_clip: bool = True,
        rolloff: bool = False,
        size: int = 1024,
        blend_blackpoint: bool = True,
    ) -> None:
        """Set the response to the SMPTE 2084 perceptual quantizer (PQ) function.

        This response is special in that it depends on the actual black
        and white level of the display.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0..white_cdm2
            white_cdm2 (float, optional): White level in candelas per square
                meter, defaults to 100.
            master_black_cdm2 (float, optional): Used to normalize PQ values.
                Defaults to 0.
            master_white_cdm2 (float, optional): Used to normalize PQ values.
                Defaults to 10000.
            use_alternate_master_white_clip (bool, optional): If True, uses the
                alternate master white clip. Defaults to True.
            rolloff (bool, optional): If True, applies the rolloff BT.2390.
                Defaults to False.
            size (int, optional): Number of steps. Recommended >= 1024.
            blend_blackpoint (bool, optional): If True, applies black point
                blending. Defaults to True.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_smpte2084_trc(
                XYZbp[1],
                white_cdm2,
                master_black_cdm2,
                master_white_cdm2,
                use_alternate_master_white_clip,
                rolloff,
                size,
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_trc_tags(
        self, identical: bool = False, power: None | float | Callable = None
    ) -> None:
        """Set the [rgb]TRC tags.

        Args:
            identical (bool, optional): If True, all channels will have the
                same TRC tag. Defaults to False.
            power (None | float | Callable, optional): If provided, sets the
                TRC to a power curve. Defaults to None, which means no power
                curve is set.
        """
        for channel in "rgb":
            if identical and channel != "r":
                tag = self.tags.rTRC
            else:
                tag = CurveType(profile=self)
                if power:
                    tag.set_trc(
                        power, size=1 if not callable(power) and power >= 0 else 1024
                    )
            self.tags[f"{channel}TRC"] = tag

    def set_localizable_desc(
        self,
        tagname: str,
        description: str,
        languagecode: str = "en",
        countrycode: str = "US",
    ) -> None:
        """Set a localizable description tag.

        Args:
            tagname (str): The tag name to set.
            description (str): The description to set for the tag.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defaults to "US".
        """
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            self.tags[tagname] = TextDescriptionType()
            if isinstance(description, str):
                asciidesc = description.encode("ASCII", "asciize")
            else:
                asciidesc = description
            self.tags[tagname].ASCII = asciidesc
            if asciidesc != description:
                self.tags[tagname].Unicode = description
        else:
            self.set_localizable_text(tagname, description, languagecode, countrycode)

    def set_localizable_text(
        self, tagname: str, text: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set a localizable text tag.

        Args:
            tagname (str): The tag name to set.
            text (str): The text to set for the tag.
            languagecode (str, otional): The language code for the text.
                Defaults to "en".
            countrycode (str, optioanl): The country code for the text.
                Defaults to "US".
        """
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            if isinstance(text, str):
                text = text.encode("ASCII", "asciize")
            self.tags[tagname] = TextType(b"text\0\0\0\0%s\0" % text, tagname)
        else:
            self.tags[tagname] = MultiLocalizedUnicodeType()
            self.tags[tagname].add_localized_string(languagecode, countrycode, text)

    def setCopyright(  # noqa: N802
        self, copyright_: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set profile copyright.

        Args:
            copyright_ (str): The profile copyright.
            languagecode (str, optional): The language code for the copyright.
                Defaults to "en".
            countrycode (str, optional): The country code for the copyright.
                Defaults to "US".
        """
        self.set_localizable_text("cprt", copyright_, languagecode, countrycode)

    def setDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set profile description.

        Args:
            description (str): The profile description.
            languagecode (str): The language code for the description. Defaults
                to "en".
            countrycode (str): The country code for the description. Defaults
                to "US".
        """
        self.set_localizable_desc("desc", description, languagecode, countrycode)

    def setDeviceManufacturerDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set device manufacturer description.

        Args:
            description (str): The device manufacturer description.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defafults to "US".
        """
        self.set_localizable_desc("dmnd", description, languagecode, countrycode)

    def setDeviceModelDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set device model description.

        Args:
            description (str): The device model description.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defaults to "US".
        """
        self.set_localizable_desc("dmdd", description, languagecode, countrycode)

    def getCopyright(self) -> str:  # noqa: N802
        """Return profile copyright.

        Returns:
            str: The profile copyright.
        """
        return str(self.tags.get("cprt", ""))

    def getDescription(self) -> str:  # noqa: N802
        """Return profile description.

        Returns:
            str: The profile description.
        """
        return str(self.tags.get("desc", ""))

    def getDeviceManufacturerDescription(self) -> str:  # noqa: N802
        """Return device manufacturer description.

        Returns:
            str: The device manufacturer description.
        """
        return str(self.tags.get("dmnd", ""))

    def getDeviceModelDescription(self) -> str:  # noqa: N802
        """Return device model description.

        Returns:
            str: The device model description.
        """
        return str(self.tags.get("dmdd", ""))

    def getViewingConditionsDescription(self) -> str:  # noqa: N802
        """Return viewing conditions description.

        Returns:
            str: The viewing conditions description.
        """
        return str(self.tags.get("vued", ""))

    def guess_cat(self, matrix: bool = True) -> None | str | colormath.Matrix3x3:
        """Get or guess chromatic adaptation transform.

        Args:
            matrix (bool): If 'matrix' is True, and 'arts' tag is present,
                return actual matrix instead of name if no match to known
                matrices.

        Returns:
            None | str | colormath.Matrix3x3: The guessed chromatic adaptation
                transform, either as a string name or a Matrix3x3 object.
                Returns None if no CAT can be guessed.
        """
        illuminant = list(self.illuminant.values())
        if isinstance(self.tags.get("chad"), ChromaticAdaptionTag):
            return colormath.guess_cat(
                self.tags.chad, self.tags.chad.inverted() * illuminant, illuminant
            )
        if isinstance(self.tags.get("arts"), ChromaticAdaptionTag):
            return self.tags.arts.get_cat() or (matrix and self.tags.arts)
        return None

    def is_same(
        self,
        profile: bytes | str | pathlib.Path | BinaryIO | TextIO,
        force_calculation: bool = False,
    ) -> bool:
        """Compare the ID of profiles.

        Returns a boolean indicating if the profiles have the same ID.

        profile can be a ICCProfile instance, a binary string
        containing profile data, a filename or a file object.

        Args:
            profile (str | bytes | path.Path | BinaryIO | TextIO | ICCProfile ):
                The profile to compare with.
            force_calculation (bool, optional): If True, forces recalculation
                of the ID. Defautls to False.

        Returns:
            bool: True if the profiles have the same ID, False otherwise.
        """
        if not isinstance(profile, self.__class__):
            profile = self.__class__(profile)
        if force_calculation or self.ID == b"\0" * 16:
            id1 = self.calculate_id(False)
        else:
            id1 = self.ID
        if force_calculation or profile.ID == b"\0" * 16:
            id2 = profile.calculate_id(False)
        else:
            id2 = profile.ID
        return id1 == id2

    def load(self) -> None:
        """Load the profile from the file object.

        Normally, you don't need to call this method, since the ICCProfile
        class automatically loads the profile when necessary (load does
        nothing if the profile was passed in as a binary string).
        """
        if self.is_loaded or not self._file:
            return
        if self._file.closed:
            self._file = open(self._file.name, "rb")  # noqa: SIM115
            self._file.seek(len(self._data))
        read_size = self.size - len(self._data)
        if read_size > 0:
            self._data += self._file.read(read_size)
        self._file.close()
        self.is_loaded = True

    def print_info(self) -> None:
        """Print profile information to stdout."""
        print("=" * 80)
        print("ICC profile information")
        print("-" * 80)
        print("File name:", os.path.basename(self.filename or ""))
        for label, value in self.get_info():
            if not value:
                print(label)
            else:
                print(label + ":", value)

    @staticmethod
    def add_device_info(info: DictList, device: dict, level: int = 1) -> None:
        """Add a device structure (see profile header) to info dict.

        Args:
            info (DictList): The dictionary to add the device information to.
            device (dict): The device structure from the profile header.
            level (int, optional): Indentation level for the device info.
                Defaults to 1.
        """
        indent = " " * 4 * level
        info[f"{indent}Manufacturer"] = "0x{}".format(
            binascii.hexlify(device.get("manufacturer", b"")).upper().decode()
        )
        if (
            len(device.get("manufacturer", b"")) == 4
            and device["manufacturer"][0:2] == b"\0\0"
            and device["manufacturer"][2:4] != b"\0\0"
        ):
            mnft_id = device["manufacturer"][3:4] + device["manufacturer"][2:3]
            mnft_id = edid.parse_manufacturer_id(mnft_id)
            manufacturer = edid.get_manufacturer_name(mnft_id)  # this is str
        else:
            manufacturer = (
                re.sub(b"[^\x20-\x7e]", b"", device.get("manufacturer", b""))
            ).decode()
            if manufacturer != device.get("manufacturer"):
                manufacturer = None
            else:
                manufacturer = f"'{manufacturer.decode()}'"
        if manufacturer is not None:
            info[f"{indent}Manufacturer"] += f" {manufacturer}"
        info[f"{indent}Model"] = hexrepr(device.get("model", ""))
        attributes = device.get("attributes", {})
        info[f"{indent}Media attributes"] = ", ".join(
            [
                {True: "Reflective"}.get(attributes.get("reflective"), "Transparency"),
                {True: "Glossy"}.get(attributes.get("glossy"), "Matte"),
                {True: "Positive"}.get(attributes.get("positive"), "Negative"),
                {True: "Color"}.get(attributes.get("color"), "Black & white"),
            ]
        )

    def get_info(self) -> list:
        """Return a list of profile information as tuples.

        The tuples are of the form (label, value), where label is a string
        describing the information and value is the corresponding value.
        If the value is None or empty, the label is returned without a value.
        This method is useful for displaying profile information in a
        user-friendly way.

        Returns:
            list: A list of tuples containing profile information.
        """
        info = DictList()
        info["Size"] = f"{int(self.size):d} Bytes ({self.size / 1024.0:.2f} KiB)"
        info["Preferred CMM"] = hexrepr(self.preferredCMM, CMMS)
        info["ICC version"] = f"{self.version}"
        info["Profile class"] = PROFILE_CLASS.get(self.profileClass, self.profileClass)
        info["Color model"] = self.colorSpace.decode()
        info["Profile connection space (PCS)"] = self.connectionColorSpace.decode()
        info["Created"] = "{:%Y-%m-%d %H:%M:%S}".format(self.dateTime)  # noqa: UP032
        info["Platform"] = PLATFORM.get(self.platform, hexrepr(self.platform))
        info["Is embedded"] = {True: "Yes"}.get(self.embedded, "No")
        info["Can be used independently"] = {True: "Yes"}.get(self.independent, "No")
        info["Device"] = ""
        ICCProfile.add_device_info(info, self.device)
        info["Default rendering intent"] = {
            0: "Perceptual",
            1: "Media-relative colorimetric",
            2: "Saturation",
            3: "ICC-absolute colorimetric",
        }.get(self.intent, "Unknown")
        info["PCS illuminant XYZ"] = " ".join(
            [
                " ".join([f"{v * 100:6.2f}" for v in list(self.illuminant.values())]),
                "(xy {},".format(
                    " ".join(f"{v:6.4f}" for v in self.illuminant.xyY[:2])
                ),
                "CCT {:d}K)".format(  # noqa: UP032
                    int(colormath.XYZ2CCT(*list(self.illuminant.values()))) or 0
                ),
            ]
        )
        info["Creator"] = hexrepr(self.creator, MANUFACTURERS)
        info["Checksum"] = f"0x{binascii.hexlify(self.ID).upper().decode()}"
        calculated_id = self.calculate_id(False)
        if self.ID != b"\0" * 16:
            info["    Checksum OK"] = {True: "Yes"}.get(calculated_id == self.ID, "No")
        if calculated_id != self.ID:
            info["    Calculated checksum"] = (
                f"0x{binascii.hexlify(calculated_id).upper().decode()}"
            )
        for sig in self.tags:
            tag = self.tags[sig]
            name = TAGS.get(sig, f"'{sig}'")
            if isinstance(tag, ChromaticAdaptionTag):
                info[name] = self.guess_cat(False) or "Unknown"
                name = "    Matrix"
                for i, row in enumerate(tag):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
            elif isinstance(tag, ChromaticityType):
                info["Chromaticity (illuminant-relative)"] = ""
                for i, channel in enumerate(tag.channels):
                    if self.colorSpace.endswith(b"CLR"):
                        colorant_name = ""
                    else:
                        colorant_name = "({}) ".format(
                            self.colorSpace[i : i + 1].decode("utf-8")
                        )
                    info[f"    Channel {i + 1:d} {colorant_name}xy"] = " ".join(
                        f"{v:6.4f}" for v in channel
                    )
            elif isinstance(tag, ColorantTableType):
                info["Colorants (PCS-relative)"] = ""
                for colorant_name in tag:
                    colorant = tag[colorant_name]
                    values = list(colorant.values())
                    if "".join(list(colorant.keys())) == "Lab":
                        values = colormath.Lab2XYZ(*values)
                    else:
                        values = [v / 100.0 for v in values]
                    XYZxy = [" ".join(f"{v:6.2f}" for v in list(colorant.values()))]  # noqa: N806
                    if values != [0, 0, 0]:
                        XYZxy.append(
                            "(xy {})".format(
                                " ".join(
                                    f"{v:6.4f}" for v in colormath.XYZ2xyY(*values)[:2]
                                )
                            )
                        )
                    colorant_name = colorant_name.decode()
                    info[
                        "    {} {}".format(
                            colorant_name, "".join(list(colorant.keys()))
                        )
                    ] = " ".join(XYZxy)
            elif isinstance(tag, ParametricCurveType):
                params = "".join(sorted(tag.params.keys()))
                tag_params = dict(list(tag.params.items()))
                for key in tag_params:
                    value = tag_params[key]
                    value = f"{value:3.2f}" if key == "g" else f"{value:.6f}"
                    value = value.rstrip("0").rstrip(".")
                    if key == "g" and "." not in value:
                        value += ".0"
                    tag_params[key] = value
                tag_params["E"] = sig[0].upper()
                if params == "g":
                    info[name] = f"Gamma {tag_params['g']}"
                else:
                    info[name] = ""
                if params == "abg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = "Y = 0"
                elif params == "abcg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {c}".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = (
                        f"Y = {tag_params['c']}"
                    )
                elif params == "abcdg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E}".format(**tag_params)
                    )
                elif params == "abcdefg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {e}".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E} + {f}".format(**tag_params)
                    )
                if params != "g":
                    tag = tag.get_trc()
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice_=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    elif transfer_function[1] >= 0.95:
                        value = "≈ {} (Δ {:.2%})".format(  # noqa: UP032
                            transfer_function[0][0],
                            1 - transfer_function[1],
                        )
                    else:
                        value = "Unknown"
                    info["    Transfer function"] = value
            elif isinstance(tag, CurveType):
                if len(tag) == 1:
                    value = (f"{tag[0]:3.2f}").rstrip("0").rstrip(".")
                    if "." not in value:
                        value = f"{value}.0"
                    info[name] = f"Gamma {value}"
                elif len(tag):
                    info[name] = ""
                    info["    Number of entries"] = f"{len(tag):d}"
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice_=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    elif transfer_function[1] >= 0.95:
                        value = "≈ {} (Δ {:.2%})".format(  # noqa: UP032
                            transfer_function[0][0],
                            1 - transfer_function[1],
                        )
                    else:
                        value = "Unknown"
                    info["    Transfer function"] = value
                    info["    Minimum Y"] = f"{tag[0] / 65535.0 * 100:6.4f}"
                    info["    Maximum Y"] = f"{tag[-1] / 65535.0 * 100:6.2f}"
            elif isinstance(tag, DictType):
                name = "Metadata" if sig == "meta" else "Generic name-value data"
                info[name] = ""
                for key in tag:
                    record = tag.get(key)
                    value = record.get("value")
                    if value and key == "prefix":
                        value = "\n".join(value.split(","))
                    info[f"    {key}"] = value
                    elements = {}
                    for subkey in ("display_name", "display_value"):
                        entry = record.get(subkey)
                        if isinstance(entry, MultiLocalizedUnicodeType):
                            for language in entry:
                                countries = entry[language]
                                for country in countries:
                                    value = countries[country]
                                    if country.strip("\0 "):
                                        country = f"/{country}"
                                    loc = f"{language}{country}"
                                    if loc not in elements:
                                        elements[loc] = {}
                                    elements[loc][subkey] = value
                    for loc in elements:
                        items = elements[loc]
                        if len(items) > 1:
                            value = "{} = {}".format(*items.values())
                        elif "display_name" in items:
                            value = "{}".format(items["display_name"])
                        else:
                            value = " = {}".format(items["display_value"])
                        info[f"        {loc}"] = value
            elif isinstance(tag, LUT16Type):
                info[name] = ""
                name = "    Matrix"
                for i, row in enumerate(tag.matrix):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
                info["    Input Table"] = ""
                info["        Channels"] = f"{int(tag.input_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.input_entries_count):d}"
                )
                info["    Color Look Up Table"] = ""
                info["        Grid Steps"] = f"{int(tag.clut_grid_steps):d}"
                info["        Entries"] = "{:d}".format(  # noqa: UP032
                    int(tag.clut_grid_steps**tag.input_channels_count)
                )
                info["    Output Table"] = ""
                info["        Channels"] = f"{int(tag.output_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.output_entries_count):d}"
                )
            elif isinstance(tag, MakeAndModelType):
                info[name] = ""
                manufacturer_code = tag.manufacturer
                manufacturer_name = edid.get_manufacturer_name(
                    edid.parse_manufacturer_id(manufacturer_code.ljust(2, b"\0")[:2])
                )
                info["    Manufacturer"] = "0x{} {}".format(
                    binascii.hexlify(manufacturer_code).decode("utf-8").upper(),
                    manufacturer_name or "",
                )
                info["    Model"] = "0x{}".format(
                    binascii.hexlify(tag.model).decode("utf-8").upper()
                )
            elif isinstance(tag, MeasurementType):
                info[name] = ""
                info["    Observer"] = tag.observer.description
                info["    Backing XYZ"] = " ".join(
                    f"{v:6.2f}" for v in list(tag.backing.values())
                )
                info["    Geometry"] = tag.geometry.description
                info["    Flare"] = f"{tag.flare:.2%}"
                info["    Illuminant"] = tag.illuminantType.description
            elif isinstance(tag, MultiLocalizedUnicodeType):
                info[name] = ""
                for language in tag:
                    countries = tag[language]
                    for country in countries:
                        value = countries[country]
                        country = "/" + country if country.strip("\0 ") else ""
                        info[f"    {language}{country}"] = value
            elif isinstance(tag, NamedColor2Type):
                info[name] = ""
                info["    Device color components"] = f"{int(tag.deviceCoordCount):d}"
                info["    Colors (PCS-relative)"] = (
                    f"{int(tag.colorCount):d} ({len(tag.tagData):d} Bytes) "
                )
                i = 1
                for k in tag:
                    v = tag[k]
                    pcsout = []
                    for _kk in v.pcs:
                        vv = v.pcs[_kk]
                        pcsout.append(f"{vv:03.2f}")
                    devout = [f"{vv:03.2f}" for vv in v.device]
                    formatstr = (
                        f"        {{:0{len(str(tag.colorCount)):d}}} {{}}{{}}{{}}"
                    )
                    key = formatstr.format(i, tag.prefix, k, tag.suffix)
                    info[key] = "{} {}".format(
                        "".join(list(v.pcs.keys())),
                        " ".join(pcsout),
                    )
                    if self.colorSpace != self.connectionColorSpace or " ".join(
                        pcsout
                    ) != " ".join(devout):
                        info[key] += " ({} {})".format(
                            self.colorSpace, " ".join(devout)
                        )
                    i += 1
            elif isinstance(tag, ProfileSequenceDescType):
                info[name] = ""
                for i, desc in enumerate(tag):
                    info[" " * 4 + f"{i + 1:d}"] = ""
                    ICCProfile.add_device_info(info, desc, 2)
                    for desc_type in ("dmnd", "dmdd"):
                        description = str(desc[desc_type])
                        if description:
                            info[" " * 8 + TAGS[desc_type]] = description
            elif isinstance(tag, Text):
                if sig == "cprt":
                    info[name] = str(tag)
                elif sig == "ciis":
                    info[name] = CIIS.get(tag, f"'{tag}'")
                elif sig == "tech":
                    print(f"tag: {tag}")
                    print(f"type(tag): {type(tag)}")
                    info[name] = TECH.get(tag, f"'{tag}'")
                elif tag.find(b"\n") > -1 or tag.find(b"\r") > -1:
                    info[name] = f"[{len(tag):d} Bytes]"
                else:
                    info[name] = tag[: 60 - len(name)] + (
                        b"...[%i more Bytes]" % (len(tag) - (60 - len(name)))
                        if len(tag) > 60 - len(name)
                        else b""
                    )
            elif isinstance(tag, TextDescriptionType):
                if not tag.get("Unicode") and not tag.get("Macintosh"):
                    info[f"{name} (ASCII)"] = tag.ASCII.decode("utf-8")
                else:
                    info[name] = ""
                    info["    ASCII"] = tag.ASCII.decode("utf-8")
                    if tag.get("Unicode"):
                        info["    Unicode"] = tag.Unicode
                    if tag.get("Macintosh"):
                        info["    Macintosh"] = tag.Macintosh
            elif isinstance(tag, VideoCardGammaFormulaType):
                info[name] = ""
                # linear = tag.is_linear()
                # info["    Is linear"] = {0: "No", 1: "Yes"}[linear]
                for key in ("red", "green", "blue"):
                    info[f"    {key.capitalize()} gamma"] = "{:.2f}".format(
                        tag[f"{key}Gamma"]
                    )
                    info[f"    {key.capitalize()} minimum"] = "{:.2f}".format(
                        tag[f"{key}Min"]
                    )
                    info[f"    {key.capitalize()} maximum"] = "{:.2f}".format(
                        tag[f"{key}Max"]
                    )
            elif isinstance(tag, VideoCardGammaTableType):
                info[name] = ""
                info["    Bitdepth"] = f"{int(tag.entrySize * 8):d}"
                info["    Channels"] = f"{int(tag.channels):d}"
                info["    Number of entries per channel"] = f"{int(tag.entryCount):d}"
                r_points, g_points, b_points, linear_points = tag.get_values()
                points = r_points, g_points, b_points
                # if r_points == g_points == b_points == linear_points:
                #     info["    Is linear".format(i)] = {
                #         True: "Yes"
                #     }.get(points[i] == linear_points, "No")
                # else:
                if True:
                    unique = tag.get_unique_values()
                    for i, channel in enumerate(tag.data):
                        scale = math.pow(2, tag.entrySize * 8) - 1
                        vmin = 0
                        vmax = scale
                        gamma = colormath.get_gamma(
                            [
                                (
                                    (len(channel) / 2 - 1)
                                    / (len(channel) - 1.0)
                                    * scale,
                                    channel[int(len(channel) / 2 - 1)],
                                )
                            ],
                            scale,
                            vmin,
                            vmax,
                            False,
                            False,
                        )
                        if gamma:
                            info[f"    Channel {i + 1} gamma at 50% input"] = (
                                f"{gamma[0]:.2f}"
                            )
                        vmin = channel[0]
                        vmax = channel[-1]
                        info[f"    Channel {i + 1} minimum"] = f"{vmin / scale:6.4%}"
                        info[f"    Channel {i + 1} maximum"] = f"{vmax / scale:6.2%}"
                        info[f"    Channel {i + 1} unique values"] = (
                            f"{len(unique[i])} @ 8 Bit"
                        )
                        info[f"    Channel {i + 1} is linear"] = (
                            "Yes" if points[i] == linear_points else "No"
                        )
            elif isinstance(tag, ViewingConditionsType):
                info[name] = ""
                info["    Illuminant"] = tag.illuminantType.description
                info["    Illuminant XYZ"] = "{} (xy {})".format(
                    " ".join(f"{v:6.2f}" for v in list(tag.illuminant.values())),
                    " ".join(f"{v:6.4f}" for v in tag.illuminant.xyY[:2]),
                )
                XYZxy = [" ".join(f"{v:6.2f}" for v in list(tag.surround.values()))]  # noqa: N806
                if list(tag.surround.values()) != [0, 0, 0]:
                    XYZxy.append(
                        "(xy {})".format(
                            " ".join(f"{v:6.4f}" for v in tag.surround.xyY[:2])
                        )
                    )
                info["    Surround XYZ"] = " ".join(XYZxy)
            elif isinstance(tag, XYZType):
                if sig == "lumi":
                    info[name] = f"{self.tags.lumi.Y:.2f} cd/m²"
                elif sig in ("bkpt", "wtpt"):
                    file_format = {"bkpt": "{:6.4f}", "wtpt": "{:6.2f}"}[sig]
                    info[name] = ""
                    if self.profileClass == b"mntr" and sig == "wtpt":
                        info["    Is illuminant"] = "Yes"
                    if self.profileClass != b"prtr":
                        label = "Illuminant-relative"
                    else:
                        label = "PCS-relative"
                    # if (self.connectionColorSpace == "Lab"
                    #    and self.profileClass == "prtr"):
                    if self.profileClass == b"prtr":
                        color = [" ".join([file_format.format(v) for v in tag.ir.Lab])]
                        info[f"    {label} Lab"] = " ".join(color)
                    else:
                        color = [
                            " ".join(
                                file_format.format(v * 100)
                                for v in list(tag.ir.values())
                            )
                        ]
                        if list(tag.ir.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])
                            color.append(f"(xy {xy})")
                            cct, delta = colormath.xy_CCT_delta(*tag.ir.xyY[:2])
                        else:
                            cct = None
                        info[f"    {label} XYZ"] = " ".join(color)
                        if cct:
                            info[f"    {label} CCT"] = f"{int(cct):d}K"
                            if delta:
                                info["        ΔE 2000 to daylight locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                            kwargs = {"daylight": False}
                            cct, delta = colormath.xy_CCT_delta(
                                *tag.ir.xyY[:2], **kwargs
                            )
                            if delta:
                                info["        ΔE 2000 to blackbody locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                    if "chad" in self.tags:
                        color = [
                            " ".join(
                                file_format.format(v * 100)
                                for v in list(tag.pcs.values())
                            )
                        ]
                        if list(tag.pcs.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.pcs.xyY[:2])
                            color.append(f"(xy {xy})")
                        info["    PCS-relative XYZ"] = " ".join(color)
                        cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2])
                        if cct:
                            info["    PCS-relative CCT"] = f"{int(cct):d}K"
                        # if delta:
                        #     info[u"        ΔE 2000 to daylight locus"] = (
                        #         f"{delta['E']:.2f}"
                        #     )
                        # kwargs = {"daylight": False}
                        # cct, delta = colormath.xy_CCT_delta(
                        #     *tag.pcs.xyY[:2], **kwargs
                        # )
                        # if delta:
                        #     info[u"        ΔE 2000 to blackbody locus"] = (
                        #         f"{delta['E']:.2f}"
                        #     )
                else:
                    info[name] = ""
                    info["    Illuminant-relative XYZ"] = " ".join(
                        [
                            " ".join(f"{v * 100:6.2f}" for v in list(tag.ir.values())),
                            "(xy {})".format(
                                " ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])
                            ),
                        ]
                    )
                    info["    PCS-relative XYZ"] = " ".join(
                        [
                            " ".join(f"{v * 100:6.2f}" for v in list(tag.values())),
                            "(xy {})".format(
                                " ".join(f"{v:6.4f}" for v in tag.xyY[:2])
                            ),
                        ]
                    )
            elif isinstance(tag, ICCProfileTag):
                info[name] = (
                    f"'{tag.tagData[:4].decode()}' [{len(tag.tagData):d} Bytes]"
                )
        return info

    def get_rgb_space(
        self, relation: str = "ir", gamma: None | bool = None
    ) -> bool | list:
        """Get RGB space from profile tags.

        Args:
            relation (str, optional): 'ir' for illuminant-relative, 'pcs' for
                PCS-relative.
            gamma (None | bool, optional): If True, return gamma values,
                otherwise TRC values.

        Returns:
            bool | list: False if the required tags are not present or a list
                containing the gamma/TRC values, the illuminant XYZ values, and
                the RGB XYZ values in the specified relation.
        """
        tags = self.tags
        if "wtpt" not in tags:
            return False
        rgb_space = [gamma or [], list(getattr(tags.wtpt, relation).values())]
        for component in ("r", "g", "b"):
            if f"{component}XYZ" not in tags or (
                not gamma
                and (
                    f"{component}TRC" not in tags
                    or not isinstance(tags[f"{component}TRC"], CurveType)
                )
            ):
                return False
            rgb_space.append(getattr(tags[f"{component}XYZ"], relation).xyY)
            if not gamma:
                if len(tags[f"{component}TRC"]) > 1:
                    rgb_space[0].append([v / 65535.0 for v in tags[f"{component}TRC"]])
                else:
                    rgb_space[0].append(tags[f"{component}TRC"][0])
        return rgb_space

    def get_chardata_bkpt(self, illuminant_relative: bool = False) -> None | list:
        """Get blackpoint from embeded characterization data ('targ' tag).

        Args:
            illuminant_relative (bool): If True, return the blackpoint
                relative to the profile's illuminant, otherwise return it
                relative to D50.

        Returns:
            None | list: A list containing the blackpoint XYZ values, or None
                if the blackpoint could not be determined.
        """
        if not isinstance(self.tags.get("targ"), Text):
            return None

        from DisplayCAL.cgats import CGATS

        ti3 = CGATS(self.tags.targ)
        if 0 not in ti3:
            return None

        black = ti3[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
        # May be several samples for black. Average them.
        if not black:
            return None

        XYZbp = [0, 0, 0]  # noqa: N806
        for sample in black.values():
            for i, component in enumerate("XYZ"):
                if "XYZ_" + component in sample:
                    XYZbp[i] += sample["XYZ_" + component] / 100.0
        for i in range(3):
            XYZbp[i] /= len(black)
        if not illuminant_relative:
            # Adapt to D50
            white = ti3.get_white_cie()
            if white:
                XYZwp = [  # noqa: N806
                    v / 100.0
                    for v in (
                        white["XYZ_X"],
                        white["XYZ_Y"],
                        white["XYZ_Z"],
                    )
                ]
            else:
                XYZwp = list(self.tags.wtpt.ir.values())  # noqa: N806
            cat = self.guess_cat() or "Bradford"
            XYZbp = colormath.adapt(*XYZbp, whitepoint_source=XYZwp, cat=cat)  # noqa: N806
        return XYZbp

    def optimize(
        self, return_bytes_saved: bool = False, update_id: bool = True
    ) -> bool | int:
        """Optimize the tag data so that shared tags are only recorded once.

        Return whether or not optimization was performed (not necessarily
        indicative of a reduction in profile size).
        If return_bytes_saved is True, return number of bytes saved instead
        (this sets the 'size' property of the profile to the new size).

        If update_id is True, a non-NULL profile ID will also be updated.

        Note that for profiles created by ICCProfile (and not read from disk),
        this will always be superfluous because they are optimized by default.

        Args:
            return_bytes_saved (bool): If True, return the number of bytes
                saved by the optimization instead of a boolean indicating
                whether optimization was performed.
            update_id (bool): If True, update the profile ID after
                optimization.

        Returns:
            bool | int: If return_bytes_saved is True, returns the number of
                bytes saved by the optimization. If return_bytes_saved is False,
                returns True if optimization was performed, otherwise False.
        """
        numoffsets = len(self._tagoffsets)
        offsets = [
            (-(numoffsets - i), tag_sig)
            for i, (offset, tag_sig) in enumerate(sorted(self._tagoffsets))
        ]
        if self._tagoffsets != offsets:
            if return_bytes_saved:
                oldsize = len(self.data)
            # Discard original offsets
            self._tagoffsets = offsets
            if update_id and self.ID != b"\0" * 16:
                self.calculate_id()
            else:
                # No longer reflects original profile
                self._delfromcache()
            if return_bytes_saved:
                self.size = len(self.data)
                return oldsize - self.size
            return True
        return 0 if return_bytes_saved else False

    def read(self, profile: str | pathlib.Path | bytes | BinaryIO | TextIO) -> None:
        """Read profile from binary string, filename or file object.

        Same as self.__init__(profile)

        Args:
            profile (str | pathlib.Path | bytes | BinaryIO | TextIO): The
                profile to read, which can be a filename, a file-like
                object, or a bytes object containing the profile data.
        """
        self.__init__(profile)

    def set_edid_metadata(self, edid: dict) -> None:
        """Set metadata from EDID.

        Key names follow the ICC meta Tag for Monitor Profiles specification
        http://www.oyranos.org/wiki/index.php?title=ICC_meta_Tag_for_Monitor_Profiles_0.1
        and the GNOME Color Manager metadata specification
        http://gitorious.org/colord/master/blobs/master/doc/metadata-spec.txt

        Args:
            edid (dict): A dictionary containing EDID data, which should
                include keys like 'manufacturer_id', 'product_id',
                'year_of_manufacture', 'week_of_manufacture', 'red_x', 'red_y',
                'green_x', 'green_y', 'blue_x', 'blue_y', 'white_x', 'white_y',
                'hash', 'manufacturer', 'monitor_name', 'serial_ascii',
                'serial_32', and 'gamma'.
        """
        if "meta" not in self.tags:
            self.tags.meta = DictType()
        spec_prefixes = "EDID_"
        prefix = self.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        # OpenICC keys (some shared with GCM)
        self.tags.meta.update(
            (
                ("prefix", ",".join(prefixes)),
                ("EDID_mnft", edid["manufacturer_id"]),
                ("EDID_mnft_id", struct.unpack(">H", edid["edid"][8:10])[0]),
                ("EDID_model_id", edid["product_id"]),
                (
                    "EDID_date",
                    "{:04d}-T{:d}".format(
                        int(edid["year_of_manufacture"]),
                        int(edid["week_of_manufacture"]),
                    ),
                ),
                ("EDID_red_x", edid["red_x"]),
                ("EDID_red_y", edid["red_y"]),
                ("EDID_green_x", edid["green_x"]),
                ("EDID_green_y", edid["green_y"]),
                ("EDID_blue_x", edid["blue_x"]),
                ("EDID_blue_y", edid["blue_y"]),
                ("EDID_white_x", edid["white_x"]),
                ("EDID_white_y", edid["white_y"]),
            )
        )
        manufacturer = edid.get("manufacturer")
        if manufacturer:
            self.tags.meta["EDID_manufacturer"] = manufacturer
        if "gamma" in edid:
            self.tags.meta["EDID_gamma"] = edid["gamma"]
        monitor_name = edid.get("monitor_name", edid.get("ascii"))
        if monitor_name:
            self.tags.meta["EDID_model"] = monitor_name
        if edid.get("serial_ascii"):
            self.tags.meta["EDID_serial"] = edid["serial_ascii"]
        elif edid.get("serial_32"):
            # don't try to convert the following ``str`` to ``bytes``.
            # the edid["serial_32"] is a huge number and bytes({int}) is not working
            # like str({int}). What it tries is to create a b"\0" * {int}.
            self.tags.meta["EDID_serial"] = str(edid["serial_32"])
        # Gnome Color Management keys
        self.tags.meta["EDID_md5"] = edid["hash"]

    def set_gamut_metadata(
        self, gamut_volume: None | float = None, gamut_coverage: None | dict = None
    ) -> None:
        """Set gamut volume and coverage metadata keys.

        Args:
            gamut_volume (None | float, optional): The gamut volume in cubic
                colorspace units (L*a*b*).
            gamut_coverage (None | dict, optional): A dictionary with gamut
                coverage factors for different color spaces, e.g.
                {'sRGB': 0.95, 'AdobeRGB': 0.85}.
        """
        if not gamut_volume and not gamut_coverage:
            return
        if "meta" not in self.tags:
            self.tags.meta = DictType()
        # Update meta prefix
        prefix = self.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or "GAMUT_").split(",")
        if "GAMUT_" not in prefixes:
            prefixes.append("GAMUT_")
        self.tags.meta["prefix"] = ",".join(prefixes)
        if gamut_volume:
            # Set gamut size
            self.tags.meta["GAMUT_volume"] = gamut_volume
        if gamut_coverage:
            # Set gamut coverage
            for key in gamut_coverage:
                factor = gamut_coverage[key]
                self.tags.meta[f"GAMUT_coverage({key})"] = factor

    def write(self, stream_or_filename: None | str | BinaryIO = None) -> None:
        """Write profile to stream.

        This will re-assemble the various profile parts (header,
        tag table and data) on-the-fly.

        Args:
            stream_or_filename (None | str | BinaryIO): The stream or
                filename to write the profile to. If None, the profile will
                be written to the filename it was loaded from.
        """
        if not stream_or_filename:
            if self._file and not self._file.closed:
                self.close()
            stream_or_filename = self.filename
        if isinstance(stream_or_filename, str):
            with open(stream_or_filename, "wb") as stream:
                if not self.filename:
                    self.filename = stream_or_filename
                stream.write(self.data)
        else:
            stream_or_filename.write(self.data)

    def __getattribute__(self, name: str) -> Any:  # noqa: ANN401
        """Get attribute, but also update the cache if necessary.

        Args:
            name (str): The name of the attribute to get.

        Returns:
            Any: The value of the attribute.
        """
        if name == "write" or name.startswith(("set", "apply")):
            # No longer reflects original profile
            self._delfromcache()
        return object.__getattribute__(self, name)

    def _delfromcache(self) -> None:
        """Remove ourselves from the cache."""
        # Make double sure to remove ourselves from the cache
        if self._key and self._key in _ICCPROFILE_CACHE:
            with contextlib.suppress(KeyError):
                del _ICCPROFILE_CACHE[self._key]
                # GC was faster
