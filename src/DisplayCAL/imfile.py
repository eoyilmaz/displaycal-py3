# -*- coding: utf-8 -*-


import math
import os
import struct
import time
import zlib

from DisplayCAL.meta import name as appname, version
from DisplayCAL.util_str import safe_str


TIFF_TAG_TYPE_BYTE = 1
TIFF_TAG_TYPE_ASCII = 2
TIFF_TAG_TYPE_WORD = 3
TIFF_TAG_TYPE_DWORD = 4
TIFF_TAG_TYPE_RATIONAL = 5  # 2 DWORDs


def tiff_get_header(w, h, samples_per_pixel, bitdepth):
    # Very helpful: http://www.fileformat.info/format/tiff/corion.htm

    header = []
    header.append(b"MM\0*")  # Note: We use big-endian byte order

    # Offset of image directory
    header.append(b"\0\0\0\x08")

    pixelcount = w * h * samples_per_pixel
    if bitdepth == 16:
        bytecount = pixelcount * 2
    else:
        bytecount = pixelcount

    # Image file directory (IFD)

    # PhotometricInterpretation
    if samples_per_pixel == 3:
        pmi = 2  # RGB
    else:
        pmi = 5  # Separated (usually CMYK)

    # Tag, type, length, offset or data, is data (otherwise offset)
    if w > 65535:
        tag_type_w = TIFF_TAG_TYPE_DWORD
    else:
        tag_type_w = TIFF_TAG_TYPE_WORD
    if h > 65535:
        tag_type_h = TIFF_TAG_TYPE_DWORD
    else:
        tag_type_h = TIFF_TAG_TYPE_WORD
    ifd = [
        (0x100, tag_type_w, 1, w, True),  # ImageWidth
        (0x101, tag_type_h, 1, h, True),  # ImageLength
        (0x106, TIFF_TAG_TYPE_WORD, 1, pmi, True),  # PhotometricInterpretation
        (0x115, TIFF_TAG_TYPE_WORD, 1, samples_per_pixel, True),  # SamplesPerPixel
        (0x117, TIFF_TAG_TYPE_DWORD, 1, bytecount, True),  # StripByteCounts
    ]
    # BitsPerSample
    ifd.append((0x102, TIFF_TAG_TYPE_WORD, 3, 10 + (len(ifd) + 2) * 12 + 4, False))
    # StripOffsets
    ifd.append((0x111, TIFF_TAG_TYPE_WORD, 1, 10 + (len(ifd) + 1) * 12 + 4 + 6, True))

    ifd.sort()  # Must be ascending order!

    header.append(struct.pack(">H", len(ifd)))  # Number of entries

    for tag, tagtype, length, payload, is_data in ifd:
        header.append(struct.pack(">H", tag))
        header.append(struct.pack(">H", tagtype))
        header.append(struct.pack(">I", length))
        if is_data and tagtype == 3:
            # A word left-aligned in a dword
            header.append(struct.pack(">H", payload))
            header.append(b"\0\0")
        else:
            header.append(struct.pack(">I", payload))

    # PlanarConfiguration default is 1 = RGBRGBRGB...

    # End of IFD
    header.append(b"\0" * 4)

    # BitsPerSample (6 bytes)
    header.append(struct.pack(">H", bitdepth) * 3)

    return b"".join(header)


def write(
    data, stream_or_filename, bitdepth=16, format=None, dimensions=None, extrainfo=None
):
    Image(data, bitdepth, extrainfo).write(stream_or_filename, format, dimensions)


def write_rgb_clut(stream_or_filename, clutres=33, bitdepth=16, format=None):
    clut = []
    for R in range(clutres):
        for G in range(clutres):
            clut.append([])
            for B in range(clutres):
                RGB = [v * (1.0 / (clutres - 1)) for v in (R, G, B)]
                clut[-1].append([v * (2**bitdepth - 1) for v in RGB])
    write(clut, stream_or_filename, bitdepth, format)


class Image:
    """Write 8 or 16 bit image files in DPX, PNG or TIFF format.

    Writing of single color images is highly optimized when using a single
    pixel as image data and setting dimensions explicitly.

    """

    def __init__(self, data, bitdepth=16, extrainfo=None):
        self.bitdepth = bitdepth
        self.data = data
        self.extrainfo = extrainfo or {}

    def _pack(self, n):
        n = int(round(n))
        if self.bitdepth == 16:
            data = struct.pack(">H", n)
        elif self.bitdepth == 8:
            data = n.to_bytes(1, "big")
        else:
            raise ValueError("Unsupported bitdepth: %r" % self.bitdepth)
        return data

    def _write_dpx(self, stream, dimensions=None):
        # Very helpful: http://www.fileformat.info/format/dpx/egff.htm
        # http://www.simplesystems.org/users/bfriesen/dpx/S268M_Revised.pdf

        # Generic file header (768 bytes)
        stream.write(b"SDPX")  # Magic number
        stream.write(struct.pack(">I", 8192))  # Offset to image data
        stream.write(b"V2.0\0\0\0\0")  # ASCII version

        # Optimize for single color
        optimize = len(self.data) == 1 and len(self.data[0]) == 1 and dimensions

        # Image data
        imgdata = []
        # 10-bit code adapted from GraphicsMagick dpx.c:WriteSamples
        if self.bitdepth == 10:
            shifts = (22, 12, 2)  # RGB
        for _i, scanline in enumerate(self.data):
            if self.bitdepth == 10:
                packed = []
                for RGB in scanline:
                    packed_u32 = 0
                    for datum, sample in enumerate(RGB):
                        packed_u32 |= sample << shifts[datum]
                    packed.append(struct.pack(">I", packed_u32))
                scanline = b"".join(packed)
            else:
                scanline = b"".join(
                    b"".join(self._pack(v) for v in RGB) for RGB in scanline
                )
            if not optimize:
                # Pad lines with binary zeros so they end on 4-byte boundaries
                scanline = scanline.ljust(
                    int(math.ceil(len(scanline) / 4.0)) * 4, b"\0"
                )
            imgdata.append(scanline)
        imgdata = "".join(imgdata)
        if optimize:
            # Optimize for single color
            imgdata *= dimensions[0]
            # Pad lines with binary zeros so they end on 4-byte boundaries
            imgdata = imgdata.ljust(int(math.ceil(len(imgdata) / 4.0)) * 4, b"\0")
            imgdata *= dimensions[1]
            w, h = dimensions
        else:
            w, h = len(self.data[0]), len(self.data)

        # Generic file header (cont.)
        stream.write(struct.pack(">I", 8192 + len(imgdata)))  # File size
        stream.write(b"\0\0\0\1")  # DittoKey (1 = not same as previous frame)
        stream.write(
            struct.pack(">I", 768 + 640 + 256)
        )  # Generic section header length
        stream.write(
            struct.pack(">I", 256 + 128)
        )  # Industry-specific section header length
        stream.write(struct.pack(">I", 0))  # User-defined data length
        stream.write(safe_str(stream.name or b"").ljust(100, b"\0")[-100:])  # File name
        # Date & timestamp
        tzoffset = round(
            (time.mktime(time.localtime()) - time.mktime(time.gmtime())) / 60.0 / 60.0
        )
        if tzoffset < 0:
            tzoffset = b"%.2i" % tzoffset
        else:
            tzoffset = b"+%.2i" % tzoffset
        stream.write(
            time.strftime("%Y:%m:%d:%H:%M:%S").encode() + tzoffset.encode() + b"\0\0"
        )
        stream.write(
            safe_str(b"%s %s" % (appname, version)).ljust(100, b"\0")
        )  # Creator
        stream.write(b"\0" * 200)  # Project
        stream.write(b"\0" * 200)  # Copyright
        stream.write(b"\xff" * 4)  # EncryptKey 0xffffffff = not encrypted
        stream.write(b"\0" * 104)  # Reserved

        # Generic image header (640 bytes)
        stream.write(b"\0\0")  # Orientation 0 = left to right, top to bottom
        stream.write(b"\0\1")  # Number of image elements
        stream.write(struct.pack(">I", w))  # Pixels per line
        stream.write(struct.pack(">I", h))  # Lines per image element

        # Generic image header - image element
        stream.write(b"\0" * 4)  # 0 = unsigned data
        stream.write(b"\0" * 4)  # Reference low data code value
        stream.write(b"\xff" * 4)  # Reference low quantity
        stream.write(
            struct.pack(">I", 2**self.bitdepth - 1)
        )  # Reference high data code value
        stream.write(b"\xff" * 4)  # Reference high quantity
        stream.write(chr(50).encode())  # Descriptor 50 = RGB
        stream.write(b"\2")  # Transfer 2 = linear
        stream.write(b"\2")  # Colorimetric 2 = not applicable
        stream.write(chr(self.bitdepth).encode())  # BitSize
        stream.write(b"\0\1")  # Packing 1 = filled 32-bit words
        stream.write(b"\0\0")  # Encoding 0 = not encoded
        stream.write(struct.pack(">I", 8192))  # Image data offset
        stream.write(b"\0" * 4)  # End of line padding
        stream.write(b"\0" * 4)  # End of image padding
        stream.write(b"RGB / Linear".ljust(32, b"\0"))  # Description

        # Seven additional unused image elements
        stream.write(b"\0" * 72 * 7)

        # Generic image header (cont.)
        stream.write(b"\0" * 52)  # Reserved

        # Generic image source header (256 bytes)
        sw, sh = [
            self.extrainfo.get("original_" + dim, locals()[dim[0]])
            for dim in ("width", "height")
        ]
        # X offset
        stream.write(struct.pack(">I", self.extrainfo.get("offset_x", (sw - w) / 2)))
        # Y offset
        stream.write(struct.pack(">I", self.extrainfo.get("offset_y", (sh - h) / 2)))
        # X center
        stream.write(struct.pack(">f", self.extrainfo.get("center_x", sw / 2.0)))
        # Y center
        stream.write(struct.pack(">f", self.extrainfo.get("center_y", sh / 2.0)))
        stream.write(struct.pack(">I", sw))  # X original size
        stream.write(struct.pack(">I", sh))  # Y original size
        stream.write(b"\0" * 100)  # Source image file name
        stream.write(b"\0" * 24)  # Source image date & timestamp
        stream.write(b"\0" * 32)  # Input device name
        stream.write(b"\0" * 32)  # Input device serial number
        stream.write(b"\0" * 2 * 4)  # Border
        stream.write(b"\0\0\0\1" * 2)  # Pixel aspect ratio
        stream.write(b"\xff" * 4)  # X scanned size
        stream.write(b"\xff" * 4)  # Y scanned size
        stream.write(b"\0" * 20)  # Reserved

        # Industry-specific film info header (256 bytes)
        stream.write(b"\0" * 2)  # Film mfg. ID code
        stream.write(b"\0" * 2)  # Film type
        stream.write(b"\0" * 2)  # Offset in perfs
        stream.write(b"\0" * 6)  # Prefix
        stream.write(b"\0" * 4)  # Count
        stream.write(b"\0" * 32)  # Format
        # Frame position in sequence
        stream.write(struct.pack(">I", self.extrainfo.get("frame_position", 2**32 - 1)))
        # Sequence length
        stream.write(
            struct.pack(">I", self.extrainfo.get("sequence_length", 2**32 - 1))
        )
        # Held count
        stream.write(struct.pack(">I", self.extrainfo.get("held_count", 1)))
        # Frame rate of original
        if "frame_rate" in self.extrainfo:
            stream.write(struct.pack(">f", self.extrainfo["frame_rate"]))
        else:
            stream.write(b"\xff" * 4)
        # Shutter angle of camera in degrees
        stream.write(b"\xff" * 4)
        stream.write(b"\0" * 32)  # Frame identification - e.g. keyframe
        stream.write(b"\0" * 100)  # Slate
        stream.write(b"\0" * 56)  # Reserved

        # Industry-specific TV info header (128 bytes)
        # SMPTE time code
        stream.write(
            b"".join(
                chr(int(str(v), 16)).encode()
                for v in self.extrainfo.get("timecode", [b"ff"] * 4)
            )
        )
        stream.write(b"\xff" * 4)  # User bits
        stream.write(b"\xff")  # Interlace
        stream.write(b"\xff")  # Field number
        stream.write(b"\xff")  # Video signal standard
        stream.write(b"\0")  # Zero for byte alignment
        stream.write(b"\xff" * 4)  # H sampling rate Hz
        stream.write(b"\xff" * 4)  # V sampling rate Hz
        # Temporal sampling or frame rate Hz
        if "frame_rate" in self.extrainfo:
            stream.write(struct.pack(">f", self.extrainfo["frame_rate"]))
        else:
            stream.write(b"\xff" * 4)
        stream.write(b"\xff" * 4)  # Time offset in ms from sync to 1st pixel
        stream.write(b"\xff" * 4)  # Gamma
        stream.write(b"\xff" * 4)  # Black level code value
        stream.write(b"\xff" * 4)  # Black gain
        stream.write(b"\xff" * 4)  # Breakpoint
        stream.write(b"\xff" * 4)  # Reference white level code value
        stream.write(b"\xff" * 4)  # Integration time in s
        stream.write(b"\0" * 76)  # Reserved

        # Padding so image data begins at 8K boundary
        stream.write("\0" * 6144)

        # Write image data
        stream.write(imgdata)

    def _write_png(self, stream, dimensions=None):
        # Header
        stream.write(b"\x89PNG\r\n\x1a\n")
        # IHDR image header length
        stream.write(struct.pack(">I", 13))
        # IHDR image header chunk type
        ihdr = [b"IHDR"]
        # Optimize for single color
        optimize = len(self.data) == 1 and len(self.data[0]) == 1 and dimensions
        # IHDR: width, height
        if optimize:
            w, h = dimensions
        else:
            w, h = len(self.data[0]), len(self.data)
        ihdr.extend([struct.pack(">I", w), struct.pack(">I", h)])
        # IHDR: Bit depth
        ihdr.append(self.bitdepth.to_bytes(1, "big"))
        # IHDR: Color type 2 (truecolor)
        ihdr.append(b"\2")
        # IHDR: Compression method 0 (deflate)
        ihdr.append(b"\0")
        # IHDR: Filter method 0 (adaptive)
        ihdr.append(b"\0")
        # IHDR: Interlace method 0 (none)
        ihdr.append(b"\0")
        ihdr = b"".join(ihdr)
        stream.write(ihdr)
        stream.write(struct.pack(">I", zlib.crc32(ihdr) & 0xFFFFFFFF))
        # IDAT image data chunk type
        imgdata = []
        for _i, scanline in enumerate(self.data):
            # Add a scanline, filter type 0
            imgdata.append(b"\0")
            for RGB in scanline:
                RGB = b"".join(self._pack(v) for v in RGB)
                if optimize:
                    RGB *= dimensions[0]
                imgdata.append(RGB)
        imgdata = b"".join(imgdata)
        if optimize:
            imgdata *= dimensions[1]
        imgdata = zlib.compress(imgdata, 9)
        stream.write(struct.pack(">I", len(imgdata)))
        idat = [b"IDAT"]
        idat.append(imgdata)
        idat = b"".join(idat)
        stream.write(idat)
        stream.write(struct.pack(">I", zlib.crc32(idat) & 0xFFFFFFFF))
        # IEND chunk
        stream.write(b"\0" * 4)
        stream.write(b"IEND")
        stream.write(struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF))

    def _write_tiff(self, stream, dimensions=None):
        # Very helpful: http://www.fileformat.info/format/tiff/corion.htm

        # Image data
        if len(self.data) == 1 and len(self.data[0]) == 1 and dimensions:
            # Optimize for single color
            w, h = dimensions
            imgdata = list(self.data)
            imgdata[0] *= w
            imgdata *= h
        else:
            imgdata = self.data
            w, h = len(self.data[0]), len(self.data)

        samples_per_pixel = len(self.data[0][0])

        # Header
        stream.write(tiff_get_header(w, h, samples_per_pixel, self.bitdepth))

        # Write image data
        for _i, scanline in enumerate(imgdata):
            for sample in scanline:
                stream.write(b"".join(self._pack(v) for v in sample))

    def write(self, stream_or_filename, format=None, dimensions=None):
        if not format:
            if isinstance(stream_or_filename, str):
                format = os.path.splitext(stream_or_filename)[1].lstrip(".").upper()
                if format == "TIF":
                    format += "F"
            else:
                format = "PNG"
        if not hasattr(self, "_write_" + format.lower()):
            raise ValueError("Unsupported format: %r" % format)
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")
        else:
            stream = stream_or_filename
        with stream:
            getattr(self, "_write_" + format.lower())(stream, dimensions)
