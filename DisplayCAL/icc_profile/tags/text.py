"""ICC text-family tags.

Includes `TextDescriptionType`, `TextType`, `MultiLocalizedUnicodeType`,
`SignatureType`, and `MakeAndModelType`.
"""

from __future__ import annotations

from DisplayCAL.icc_profile.codecs import (
    uInt8Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.constants import DEBUG, ENCODINGS
from DisplayCAL.icc_profile.structures import ADict, AODict
from DisplayCAL.icc_profile.tags.base import ICCProfileTag, Text


class MakeAndModelType(ICCProfileTag, ADict):
    """ICC makeAndModelType tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.update({"manufacturer": tagData[10:12], "model": tagData[14:16]})


class MultiLocalizedUnicodeType(ICCProfileTag, AODict):  # ICC v4
    """ICC v4 MultiLocalizedUnicodeType tag.

    Args:
        tagData (None | bytes, optional): Raw tag data. Defaults to None.
        tagSignature (None | str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        records_count = uInt32Number(tagData[8:12])
        record_size = uInt32Number(tagData[12:16])  # 12
        if record_size != 12:
            print(
                f"Warning (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 12, got {record_size})"
            )
            record_size = max(record_size, 12)
        records = tagData[16 : 16 + record_size * records_count]
        for _count in range(records_count):
            record = records[:record_size]
            if len(record) < 12:
                continue
            record_language_code = record[:2].decode("ascii", "replace")
            record_country_code = record[2:4].decode("ascii", "replace")
            record_length = uInt32Number(record[4:8])
            record_offset = uInt32Number(record[8:12])
            self.add_localized_string(
                record_language_code,
                record_country_code,
                str(
                    tagData[record_offset : record_offset + record_length],
                    "utf-16-be",
                    "replace",
                ),
            )
            records = records[record_size:]

    def __str__(self) -> str:
        """Return tag as string.

        Returns:
            str: The first localized string in the tag, or an empty string if
                no localized strings are available.
        """
        # TODO: Needs some work re locales
        # (currently if en-UK or en-US is not found, simply the first entry
        # is returned)
        if "en" in self:
            for country_code in ("UK", "US"):
                if country_code in self["en"]:
                    return self["en"][country_code]
            if self["en"]:
                # return first value
                return next(iter(self["en"].values()))
            return ""
        if len(self):
            # return first value of the first dictionary
            return next(iter(next(iter(self.values())).values()))
        return ""

    def add_localized_string(
        self, languagecode: str, countrycode: str, localized_string: str
    ) -> None:
        """Convenience function for adding localized strings."""
        if languagecode not in self:
            self[languagecode] = AODict()
        self[languagecode][countrycode] = localized_string.strip("\0")

    def get_localized_string(
        self, languagecode: str = "en", countrycode: str = "US"
    ) -> str:
        """Convenience function for retrieving localized strings.

        Falls back to first locale available if the requested one isn't

        Args:
            languagecode (str): The language code to retrieve the string for.
                Defaults to "en".
            countrycode (str): The country code to retrieve the string for.
                Defaults to "US".

        Returns:
            str: The localized string for the given language and country code,
                or the first available string if the requested one is not
                found.
        """
        try:
            return self[languagecode][countrycode]
        except KeyError:
            return str(self)

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data."""
        tag_data = [b"mluc", b"\0" * 4]
        records_count = 0
        for language_code in self:
            for _ in self[language_code]:
                records_count += 1
        tag_data.append(uInt32Number_tohex(records_count))
        record_size = 12
        tag_data.append(uInt32Number_tohex(record_size))
        storage_offset = 16 + record_size * records_count
        storage = []
        offsets = []
        for language_code in self:
            for country_code in self[language_code]:
                tag_data.append((language_code + country_code).encode("ascii"))
                data = self[language_code][country_code].encode("UTF-16-BE")
                if data in storage:
                    offset, record_length = offsets[storage.index(data)]
                else:
                    record_length = len(data)
                    offset = len("".join(storage))
                    offsets.append((offset, record_length))
                    storage.append(data)
                tag_data.append(uInt32Number_tohex(record_length))
                tag_data.append(uInt32Number_tohex(storage_offset + offset))
        tag_data.append(
            b"".join(storage)
        )  # TODO: Are you sure that this needs to be bytes
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): Raw tag data to set.
        """


def SignatureType(tagData: bytes, tagSignature: str) -> Text:  # noqa: N802, N803
    """Generate ICC signatureType tag.

    Args:
        tagData (bytes): The raw tag data containing the signature.
        tagSignature (str): The signature of the tag.

    Returns:
        Text: An instance of the Text class representing the tag.
    """
    tag = Text(tagData[8:12].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag


class TextDescriptionType(ICCProfileTag, ADict):  # ICC v2
    """ICC textDescriptionType tag.

    Args:
        tagData (None | bytes, optional): Raw tag data. Defaults to None.
        tagSignature (None | str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.ASCII = b""
        if not tagData:
            return
        ascii_description_length = uInt32Number(tagData[8:12])
        if ascii_description_length:
            ascii_description = tagData[12 : 12 + ascii_description_length].strip(
                b"\0\n\r "
            )
            if ascii_description:
                self.ASCII = ascii_description
        unicode_offset = 12 + ascii_description_length
        self.unicodeLanguageCode = uInt32Number(
            tagData[unicode_offset : unicode_offset + 4]
        )
        unicode_description_length = uInt32Number(
            tagData[unicode_offset + 4 : unicode_offset + 8]
        )
        if unicode_description_length:
            if unicode_offset + 8 + unicode_description_length * 2 > len(tagData):
                # Damn you MS. The Unicode character count should be the number of
                # double-byte characters (including trailing unicode NUL), not the
                # number of bytes as in the profiles created by Vista and later
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part end points "
                    "past the tag data, assuming number of bytes instead "
                    "of number of characters for length"
                )
                unicode_description_length /= 2
            if (
                tagData[
                    unicode_offset + 8 + unicode_description_length : unicode_offset
                    + 8
                    + unicode_description_length
                    + 2
                ]
                == b"\0\0"
            ):
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part "
                    "seems to be a single-byte string (double-byte "
                    "string expected)"
                )
                char_bytes = 1  # fix for fubar'd desc
            else:
                char_bytes = 2
            unicode_description = tagData[
                unicode_offset + 8 : unicode_offset
                + 8
                + (unicode_description_length) * char_bytes
            ]
            try:
                if char_bytes == 1:
                    unicode_description = str(unicode_description, errors="replace")
                elif unicode_description[:2] == b"\xfe\xff":
                    # UTF-16 Big Endian
                    if DEBUG:
                        print("UTF-16 Big endian")
                    unicode_description = unicode_description[2:]
                    if (
                        len(unicode_description.split(b" "))
                        == unicode_description_length - 1
                    ):
                        print(
                            f"Warning (non-critical): '{tagData[:4]}' "
                            "Unicode part starts with UTF-16 big "
                            "endian BOM, but actual contents seem "
                            "to be UTF-16 little endian"
                        )
                        # fix fubar'd desc
                        unicode_description = str(
                            b"\0".join(unicode_description.split(b" ")),
                            "utf-16-le",
                            errors="replace",
                        )
                    else:
                        unicode_description = str(
                            unicode_description, "utf-16-be", errors="replace"
                        )
                elif unicode_description[:2] == b"\xff\xfe":
                    # UTF-16 Little Endian
                    if DEBUG:
                        print("UTF-16 Little endian")
                    unicode_description = unicode_description[2:]
                    if unicode_description[0] == b"\0":
                        print(
                            f"Warning (non-critical): '{tagData[:4]}' "
                            "Unicode part starts with UTF-16 "
                            "little endian BOM, but actual "
                            "contents seem to be UTF-16 big "
                            "endian"
                        )
                        # fix fubar'd desc
                        unicode_description = str(
                            unicode_description, "utf-16-be", errors="replace"
                        )
                    else:
                        unicode_description = str(
                            unicode_description, "utf-16-le", errors="replace"
                        )
                else:
                    if DEBUG:
                        print("ASSUMED UTF-16 Big Endian")
                    unicode_description = str(
                        unicode_description, "utf-16-be", errors="replace"
                    )
                unicode_description = unicode_description.strip("\0\n\r ")
                if unicode_description:
                    if unicode_description.find("\0") < 0:
                        self.Unicode = unicode_description
                    else:
                        print(
                            "Error (non-critical): could not decode "
                            f"'{tagData[:4]}' Unicode part - null byte(s) "
                            "encountered"
                        )
            except UnicodeDecodeError:
                print(
                    "UnicodeDecodeError (non-critical): could not "
                    f"decode '{tagData[:4]}' Unicode part"
                )
        else:
            char_bytes = 1
        mac_offset = unicode_offset + 8 + unicode_description_length * char_bytes
        self.macScriptCode = 0
        if len(tagData) > mac_offset + 2:
            self.macScriptCode = uInt16Number(tagData[mac_offset : mac_offset + 2])
            mac_description_length = ord(tagData[mac_offset + 2 : mac_offset + 3])
            if mac_description_length:
                mac_bytes = tagData[
                    mac_offset + 3 : mac_offset + 3 + mac_description_length
                ]
                try:
                    if mac_bytes[:2] in (b"\xfe\xff", b"\xff\xfe"):
                        # Some writers put UTF-16 here, byte order mark first
                        mac_description = mac_bytes.decode("utf-16", errors="replace")
                    else:
                        mac_description = str(
                            mac_bytes,
                            "mac-" + ENCODINGS["mac"][self.macScriptCode],
                            errors="replace",
                        )
                    mac_description = mac_description.strip("\0\n\r ")
                    if mac_description:
                        self.Macintosh = mac_description
                except KeyError:
                    print(
                        f"KeyError (non-critical): could not decode '{tagData[:4]}' "
                        f"Macintosh part (unsupported encoding {self.macScriptCode})"
                    )
                except LookupError:
                    print(
                        f"LookupError (non-critical): could not decode '{tagData[:4]}' "
                        "Macintosh part (unsupported encoding "
                        f"'{ENCODINGS['mac'][self.macScriptCode]}')"
                    )
                except UnicodeDecodeError:
                    print(
                        "UnicodeDecodeError (non-critical): could not decode "
                        f"'{tagData[:4]}' Macintosh part"
                    )

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data for the textDescriptionType tag.
        """
        tag_data = [
            b"desc",
            b"\0" * 4,
            uInt32Number_tohex(len(self.ASCII) + 1),  # count of ASCII chars + 1
            self.ASCII + b"\0",  # ASCII desc, \0 terminated
            uInt32Number_tohex(self.get("unicodeLanguageCode", 0)),
        ]
        if "Unicode" in self:
            tag_data.extend(
                [
                    # count of Unicode chars + 2 (UTF-16-BE BOM + trailing UTF-16 NUL,
                    #                             1 char = 2 byte)
                    uInt32Number_tohex(len(self.Unicode) + 2),
                    b"\xfe\xff" + self.Unicode.encode("utf-16-be", "replace") + b"\0\0",
                ]
            )  # Unicode desc, \0\0 terminated
        else:
            tag_data.append(uInt32Number_tohex(0))  # Unicode desc length = 0
        tag_data.append(uInt16Number_tohex(self.get("macScriptCode", 0)))
        if "Macintosh" in self:
            mac_description = self.Macintosh[:66]
            tag_data.extend(
                [
                    uInt8Number_tohex(
                        len(mac_description) + 1
                    ),  # count of Macintosh chars + 1
                    mac_description.encode(
                        "mac-" + ENCODINGS["mac"][self.get("macScriptCode", 0)],
                        "replace",
                    )
                    + (b"\0" * (67 - len(mac_description))),
                ]
            )
        else:
            tag_data.extend([b"\0", b"\0" * 67])  # Mac desc length = 0
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): The raw tag data to set.
        """

    def __str__(self) -> str:
        """Return tag as string.

        Returns:
            str: The localized string if available, otherwise the ASCII
                representation of the tag.
        """
        if "Unicode" not in self and len(str(self.ASCII)) < 67:
            # Do not use Macintosh description if ASCII length >= 67
            localized_types = ("Macintosh", "ASCII")
        else:
            localized_types = ("Unicode", "ASCII")

        for localized_type in localized_types:
            if localized_type not in self:
                continue
            value = self[localized_type]
            if not isinstance(value, str):
                # Even ASCII description may contain non-ASCII chars, so
                # assume system encoding and convert to unicode, replacing
                # unknown chars
                value = value.decode("utf-8", "replace")
            return value
        return None


def TextType(tagData: bytes, tagSignature: str) -> Text:  # noqa: N802, N803
    """Generate an ICC textType tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag, usually "text".

    Returns:
        Text: An instance of the Text class containing the tag data and
            signature.
    """
    tag = Text(tagData[8:].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag
