"""Integration with madVR's Test Pattern Generator (madTPG) for display calibration.

It supports both local and network-based communication with madVR instances,
enabling features such as 3D LUT creation, device gamma ramp manipulation, and
test pattern display.

See developers/interfaces/madTPG.h in the madVR package
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import getpass
import os
import platform
import socket
import struct
import sys
import threading
from binascii import unhexlify
from io import BytesIO, StringIO
from time import sleep, time
from typing import Any, BinaryIO, Callable, TextIO
from zlib import crc32

if sys.platform == "win32":
    import winreg

if sys.platform == "win32":
    import win32api

from DisplayCAL import colormath, worker_base
from DisplayCAL import cubeiterator as ci
from DisplayCAL import localization as lang
from DisplayCAL.config import CaseSensitiveConfigParser
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileTag,
    LUT16Type,
    TextDescriptionType,
    TextType,
)
from DisplayCAL.imfile import tiff_get_header
from DisplayCAL.meta import VERSION_STRING
from DisplayCAL.network import get_network_addr

CALLBACK = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.POINTER(None),
    ctypes.c_char_p,
    ctypes.c_ulong,
    ctypes.c_ulonglong,
    ctypes.c_char_p,
    ctypes.c_ulonglong,
    ctypes.c_bool,
)

H3D_HEADER = (
    b"3DLT\x01\x00\x00\x00DisplayCAL\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00 \x00"
    b"\x00\x00\x00\x00\x00\x08\x00\x00\x00\x08\x00\x00\x00\x08\x00\x00"
    b"\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00"
    b"\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x06\x00\x00\x00\x06"
)

MIN_VERSION = (0, 88, 20, 0)

# Search for madTPG on the local PC, connect to the first found instance
CM_ConnectToLocalInstance = 0
# Search for madTPG on the LAN, connect to the first found instance
CM_ConnectToLanInstance = 1
# Start madTPG on the local PC and connect to it
CM_StartLocalInstance = 2
# Search local PC and LAN, and let the user choose which instance to connect to
CM_ShowListDialog = 3
# Let the user enter the IP address of a PC which runs madTPG, then connect
CM_ShowIpAddrDialog = 4
# fail immediately
CM_Fail = 5

_METHOD_NAMES = (
    "ConnectEx",
    "Disable3dlut",
    "Enable3dlut",
    "EnterFullscreen",
    "GetBlackAndWhiteLevel",
    "GetDeviceGammaRamp",
    "GetSelected3dlut",
    "GetVersion",
    "IsDisableOsdButtonPressed",
    "IsFseModeEnabled",
    "IsFullscreen",
    "IsStayOnTopButtonPressed",
    "IsUseFullscreenButtonPressed",
    "LeaveFullscreen",
    "SetDisableOsdButton",
    "SetDeviceGammaRamp",
    "SetOsdText",
    "GetPatternConfig",
    "SetPatternConfig",
    "ShowProgressBar",
    "SetProgressBarPos",
    "SetSelected3dlut",
    "SetStayOnTopButton",
    "SetUseFullscreenButton",
    "ShowRGB",
    "ShowRGBEx",
    "Load3dlutFile",
    "LoadHdr3dlutFile",
    "Disconnect",
    "Quit",
    "Load3dlutFromArray256",
    "LoadHdr3dlutFromArray256",
)

_AUTONET_METHOD_NAMES = ("AddConnectionCallback", "Listen", "Announce")

_LOCK = threading.RLock()


def safe_print(*args) -> None:
    """Thread-safe print function."""
    with _LOCK:
        print(*args)


def icc_device_link_to_madvr(
    icc_device_link_filename: str,
    unity: bool = False,
    colorspace: None | str | list[float] = None,
    hdr: None | int = None,
    logfile: TextIO = sys.stdout,
    convert_video_rgb_to_clut65: bool = False,
    append_linear_cal: bool = True,
) -> bool:
    """Convert ICC device link profile to madVR 256^3 3D LUT using interpolation.

    madvr 3D LUT will be written to:
    <device link filename without extension> + '.3dlut'

    Args:
        icc_device_link_filename (str): Path to the ICC device link profile.
        unity (bool): If True, write a unity madVR 3D LUT.
        colorspace (None | str | list[float]): The target color space for the
            3D LUT. If None, the color space will be inferred from the
            filename.
        hdr (None | int): If 2, write a madVR HDR 3D LUT. If 1, write a madVR
            HDR2SDR 3D LUT. If None, write a madVR SDR 3D LUT.
        logfile (TextIO): The log file to write progress messages to.
        convert_video_rgb_to_clut65 (bool): If True, convert video RGB to
            CLUT65 format when writing the 3D LUT. This is useful for madVR's
            video RGB to CLUT65 conversion.
        append_linear_cal (bool): If True, append a madVR cal1 table to the 3D
            LUT.

    Returns:
        bool: True if the conversion was successful, False otherwise.
    """
    start_time = time()
    filename = os.path.splitext(icc_device_link_filename)[0]
    h3d_params = {}
    name = get_transfer_function_and_name(hdr, filename, h3d_params)
    colorspace = process_colorspace(colorspace, name)
    if not colorspace:
        return False

    h3d_params["Input_Primaries"] = colorspace
    h3d_params["Input_Range"] = (16, 235)
    h3d_params["Output_Range"] = (16, 235)

    # Create madVR 3D LUT
    h3d_stream = BytesIO(H3D_HEADER)
    h3dlut = H3DLUT(h3d_stream, check_lut_size=False)
    h3dlut.parametersData = h3d_params
    h3dlut.write(f"{filename}.3dlut")
    raw = open(f"{filename}.3dlut", "r+b")  # noqa: SIM115
    raw.seek(h3dlut.lutFileOffset)
    # Make sure no longer needed h3DLUT instance can be garbage collected
    del h3dlut

    fill_madvr_3dlut_with_icc_device_link(
        unity,
        logfile,
        raw,
        icc_device_link_filename,
        convert_video_rgb_to_clut65,
    )

    if append_linear_cal:
        append_calibration_table(raw)
    raw.close()

    print_lut_generation_summary(unity, colorspace, start_time, filename)
    return True


def get_transfer_function_and_name(
    hdr: None | int, filename: str, h3d_params: dict
) -> str:
    """Determine transfer function and base name for madVR 3D LUT.

    Args:
        hdr (None | int): If 2, write a madVR HDR 3D LUT. If 1, write a madVR
            HDR2SDR 3D LUT. If None, write a madVR SDR 3D LUT.
        filename (str): The base filename to use for the 3D LUT.
        h3d_params (dict): The dictionary to populate with transfer function
            parameters.

    Returns:
        str: The base name for the 3D LUT.
    """
    if filename.endswith(".HDR") or hdr == 2:
        name = os.path.splitext(filename)[0]
        h3d_params["Input_Transfer_Function"] = "PQ"
        h3d_params["Output_Transfer_Function"] = "PQ"
    elif filename.endswith(".HDR2SDR") or hdr == 1:
        name = os.path.splitext(filename)[0]
        h3d_params["Input_Transfer_Function"] = "PQ"
    else:
        name = filename
    return name


def process_colorspace(colorspace: None | str | list[float], name: str) -> list[float]:
    """Process and validate the target color space for madVR 3D LUT.

    Args:
        colorspace (None | str | list[float]): The target color space for the
            3D LUT. If None, the color space will be inferred from the
            filename.
        name (str): The base filename to use for the 3D LUT.

    Returns:
        list[float]: The processed color space primaries and whitepoint. If the
            color space is invalid, returns the original colorspace value.
    """
    if not colorspace:
        colorspace = os.path.splitext(name)[1]
        colorspace = colorspace[1:]

    if not isinstance(colorspace, (list, tuple)):
        key = {
            "BT709": "Rec. 709",
            "SMPTE_C": "SMPTE-C",
            "EBU_PAL": "PAL/SECAM",
            "BT2020": "Rec. 2020",
            "DCI_P3": "DCI P3 D65",
        }.get(colorspace)
        if not key:
            if not colorspace:
                safe_print("ERROR - no target color space suffix in filename")
            else:
                safe_print("ERROR - invalid target color space:", colorspace)
            safe_print(
                "Possible target color spaces:",
                "BT709, SMPTE_C, EBU_PAL, BT2020, DCI_P3",
            )
            return colorspace

        rgb_space = colormath.get_rgb_space(key)
        colorspace = colormath.get_rgb_space_primaries_wp_xy(rgb_space)
    colorspace = list(colorspace)

    # Use a D65 white for the 3D LUT Input_Primaries as
    # madVR can only deal correctly with D65
    # Use the same D65 xy values as written by madVR
    # 3D LUT install API (ASTM E308-01)
    colorspace[6:] = [0.31273, 0.32902]
    return colorspace


def fill_madvr_3dlut_with_icc_device_link(
    unity: bool,
    logfile: TextIO,
    raw: BinaryIO,
    icc_device_link_filename: str,
    convert_video_rgb_to_clut65: bool,
) -> None:
    """Fill madVR 3D LUT with values from ICC device link profile.

    Args:
        unity (bool): If True, write a unity madVR 3D LUT.
        logfile (TextIO): The log file to write progress messages to.
        raw (BinaryIO): The binary stream to write the 3D LUT data to.
        icc_device_link_filename (str): Path to the ICC device link profile.
        convert_video_rgb_to_clut65 (bool): If True, convert video RGB to
            CLUT65 format when writing the 3D LUT. This is useful for madVR's
            video RGB to CLUT65 conversion.
    """
    # Lookup 256^3 values through device link and fill madVR cLUT
    clutres = 256
    clutmax = clutres - 1.0
    if unity:
        logfile.write("Writing unity madVR 3D LUT...\n")
        prevperc = -1
        for i in range(clutres):
            for j in range(clutres):
                for k in range(clutres):
                    # Optimize for speed
                    b, g, r = bytes([k]), bytes([j]), bytes([i])
                    raw.write(b + b + g + g + r + r)
            perc = round(i / clutmax * 100)
            if perc > prevperc:
                logfile.write(f"\r{perc}%")
                prevperc = perc
    else:
        link = ICCProfile(icc_device_link_filename)
        # Need a worker for abort event handling
        worker = worker_base.WorkerBase()
        # icclu verbose=0 gives a speed increase
        xicclu = worker_base.XiccluMP(
            link,
            scale=clutmax,
            use_icclu=True,
            logfile=logfile,
            output_format=("<H", 65535),
            reverse=True,
            output_stream=raw,
            convert_video_rgb_to_clut65=convert_video_rgb_to_clut65,
            verbose=0,
            worker=worker,
        )
        xicclu._in = ci.Cube3D(clutres)
        logfile.write(
            "Looking up 256^3 input values through device link and "
            "writing madVR 3D LUT...\n"
        )
        xicclu.exit()
        xicclu.get()


def append_calibration_table(raw: BinaryIO) -> None:
    """Append a madVR cal1 table to the 3D LUT.

    Args:
        raw (BinaryIO): The binary stream to write the calibration table to.
    """
    # Append a MadVR cal1 table to the 3dlut.
    # This can be used to ensure that the Graphics Card VideoLuts
    # are correctly setup to match what the 3dLut is expecting.
    #
    # Note that the calibration curves are full range,
    # never TV encoded output values.
    #
    # Format is (little endian):
    #    4 byte magic number 'cal1'
    #    4 byte version = 1
    #    4 byte number per channel entries = 256
    #    4 byte bytes per entry = 2
    #    [3][256] 2 byte entry values. Tables are in RGB order
    raw.write(b"cal1")
    raw.write(struct.pack("<I", 1))
    raw.write(struct.pack("<I", 256))
    raw.write(struct.pack("<I", 2))
    # Linear (unity) calibration
    for _ in range(3):
        for j in range(256):
            raw.write(struct.pack("<H", j * 257))


def print_lut_generation_summary(
    unity: bool, colorspace: list[float], start_time: float, filename: str
) -> None:
    """Print summary after LUT generation.

    Args:
        unity (bool): Whether a unity LUT was generated.
        colorspace (list[float]): The colorspace primaries and whitepoint.
        start_time (float): The start time of the LUT generation.
        filename (str): The filename of the generated LUT.
    """
    safe_print("")
    if unity:
        msg = "Finished writing unity madVR 3D LUT in"
    else:
        msg = "Finished up-interpolating device link and writing madVR 3D LUT in"
    safe_print(msg, time() - start_time, "seconds")
    if filename.endswith(".HDR"):
        safe_print(
            "Gamut (rx ry gx gy bx by wx wy):",
            "{:.5f} {:.5f} {:.5f} {:.5f} {:.5f} {:.5f} {:.5f} {:.5f}".format(
                *tuple(colorspace)
            ),
        )


def inet_pton(ip_string: str) -> bytes:
    """Convert ip_string to packed IP representation.

    Convert an IP address in string format to the packed binary format used in
    low-level network functions.

    Args:
        ip_string (str): The IP address in string format, either IPv4 or IPv6.

    Returns:
        bytes: The packed binary representation of the IP address.
    """
    if ":" in ip_string:
        # IPv6
        return b"".join(
            [unhexlify(block.rjust(4, "0")) for block in ip_string.split(":")]
        )
    # IPv4
    return bytes(int(block) for block in ip_string.split("."))


def trunc(value: str, length: int) -> str:
    """For string types, return value truncated to length.

    Args:
        value (str): The value to be truncated.
        length (int): The maximum length of the string.

    Returns:
        str: The truncated string, or the original value if it is shorter than
            or equal to the specified length.
    """
    if isinstance(value, str) and len(repr(value)) > length:
        value = value[: length - 3 - len(str(length)) - len(repr(value)) + len(value)]
        return f"{value!r}[{length:d}]"
    return repr(value)


class H3DLUT:
    """3D LUT file format used by madVR.

    Args:
        stream_or_filename (None | str | BinaryIO, optional): The file path or
            a binary stream containing the 3D LUT data.
        check_lut_size (bool): Whether to check the size of the LUT data
            against the expected size.
    """

    # https://sourceforge.net/projects/thr3dlut

    def __init__(
        self,
        stream_or_filename: None | str | BinaryIO = None,
        check_lut_size: bool = True,
    ) -> None:
        if not stream_or_filename:
            return
        if isinstance(stream_or_filename, str):
            self.filename = stream_or_filename
            with open(stream_or_filename, "rb") as lut:
                data = lut.read()
        else:
            self.filename = None
            data = stream_or_filename.read()
        self.signature = data[:4]
        self.fileVersion = struct.unpack("<l", data[4:8])[0]
        self.programName = data[8:40].rstrip(b"\0")
        self.programVersion = struct.unpack("<q", data[40:48])[0]
        self.inputBitDepth = struct.unpack("<3l", data[48:60])
        self.inputColorEncoding = struct.unpack("<l", data[60:64])[0]
        self.outputBitDepth = struct.unpack("<l", data[64:68])[0]
        self.outputColorEncoding = struct.unpack("<l", data[68:72])[0]
        self.parametersFileOffset = struct.unpack("<l", data[72:76])[0]
        parameters_size = struct.unpack("<l", data[76:80])[0]
        self.lutFileOffset = struct.unpack("<l", data[80:84])[0]
        self.lutCompressionMethod = struct.unpack("<l", data[84:88])[0]
        if self.lutCompressionMethod != 0:
            raise ValueError(
                f"Compression method not supported: {self.lutCompressionMethod}"
            )
        self.lutCompressedSize = struct.unpack("<l", data[88:92])[0]
        self.lutUncompressedSize = struct.unpack("<l", data[92:96])[0]
        self.parametersData = {}
        for line in (
            data[
                self.parametersFileOffset : self.parametersFileOffset + parameters_size
            ]
            .rstrip(b"\0")
            .splitlines()
        ):
            item = line.decode().split(maxsplit=1)
            if len(item) == 2:
                key, values = item
                values = values.split()
                if len(values) == 1:
                    value = values[0]
                else:
                    for i, value in enumerate(values):
                        if value.isdigit():
                            values[i] = int(value)
                        elif not value.isalpha():
                            values[i] = float(value)
                    value = tuple(values)
                self.parametersData[key] = value
        self.LUTDATA = data[
            self.lutFileOffset : self.lutFileOffset + self.lutCompressedSize
        ]
        if check_lut_size and len(self.LUTDATA) != self.lutCompressedSize:
            raise ValueError(
                f"3DLUT size {len(self.LUTDATA)} "
                f"does not match expected size {self.lutCompressedSize}"
            )
        if len(data) == self.lutFileOffset + self.lutCompressedSize + 1552:
            # Calibration appendended
            self.LUTDATA += data[
                self.lutFileOffset + self.lutCompressedSize : self.lutFileOffset
                + self.lutCompressedSize
                + 1552
            ]

    @property
    def data(self) -> bytes:
        """Return the raw 3D LUT data as bytes.

        Returns:
            bytes: The raw 3D LUT data, including header and parameters.
        """
        parameters_data = []
        for key in self.parametersData:
            values = self.parametersData[key]
            if isinstance(values, str):
                value = values
            else:
                values = list(values)
                for i, value in enumerate(values):
                    if isinstance(value, float):
                        values[i] = f"{value:.5f}"
                    else:
                        values[i] = f"{value}"
                value = " ".join(values)
            parameters_data.append((f"{key} {value}").encode())
        parameters_data = b"\r\n".join(parameters_data) + b"\0"
        parameters_size = len(parameters_data)
        return b"".join(
            (
                self.signature,
                struct.pack("<l", self.fileVersion),
                self.programName.ljust(32, b"\0"),
                struct.pack("<q", self.programVersion),
                struct.pack("<3l", *self.inputBitDepth),
                struct.pack("<l", self.inputColorEncoding),
                struct.pack("<l", self.outputBitDepth),
                struct.pack("<l", self.outputColorEncoding),
                struct.pack("<l", self.parametersFileOffset),
                struct.pack("<l", parameters_size),
                struct.pack("<l", self.lutFileOffset),
                struct.pack("<l", self.lutCompressionMethod),
                struct.pack("<l", self.lutCompressedSize),
                struct.pack("<l", self.lutUncompressedSize),
                b"\0" * (self.parametersFileOffset - 96),
                parameters_data,
                b"\0"
                * (self.lutFileOffset - self.parametersFileOffset - parameters_size),
                self.LUTDATA,
            )
        )

    @property
    def source_colorspace(self) -> tuple[int, str]:
        """Return the 3D LUT source colorspace slot and name as 2-tuple.

        Returns:
            tuple[int, str]: A tuple containing the source colorspace slot
                (0 for Rec. 709, 1 for SMPTE-C, etc.) and the name of the
                colorspace (e.g., "Rec. 709", "SMPTE-C", etc.).
        """
        # Determine gamut slot only based on primaries (omit whitepoint)
        xy = list(self.parametersData.get("Input_Primaries", [])[:6])
        rgb_space_name = colormath.find_primaries_wp_xy_rgb_space_name(xy)
        return {
            "Rec. 709": 0,
            "SMPTE-C": 1,  # SMPTE RP 145 (NTSC)
            "PAL/SECAM": 2,
            "Rec. 2020": 3,
            "DCI P3": 4,
            "DCI P3 D65": 4,
        }.get(rgb_space_name), rgb_space_name

    def _get_stream(
        self, stream_or_filename: None | str | BinaryIO = None, ext: None | str = None
    ) -> BinaryIO:
        """Get a writable stream for the 3D LUT data.

        Args:
            stream_or_filename (None | str | BinaryIO, optional): The file path
                or a binary stream to write the 3D LUT data to.
            ext (str, optional): The file extension to use if a filename is
                provided. Defaults to None.

        Returns:
            BinaryIO: A writable stream for the 3D LUT data.
        """
        if not stream_or_filename:
            stream_or_filename = self.filename
            if ext:
                stream_or_filename = os.path.splitext(stream_or_filename)[0] + ext
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")  # noqa: SIM115
        else:
            stream = stream_or_filename
        return stream

    def write(self, stream_or_filename: None | str | BinaryIO = None) -> None:
        """Write 3D LUT to stream or filename.

        Args:
            stream_or_filename (None | str | BinaryIO, optional): The file path
                or a binary stream to write the 3D LUT data to. If None, uses
                the filename from the instance. If a string is provided, it
                will be used as the filename with a ".3dlut" extension.
        """
        stream = self._get_stream(stream_or_filename)
        stream.write(self.data)
        if isinstance(stream_or_filename, str):
            if not self.filename:
                self.filename = stream_or_filename
            stream.close()

    def write_devicelink(
        self, stream_or_filename: None | str | BinaryIO = None
    ) -> None:
        """Write 3D LUT to ICC device link.

        Args:
            stream_or_filename (None | str | BinaryIO, optional): The file path
                or a binary stream to write the ICC device link data to. If None,
                uses the filename from the instance. If a string is provided, it
                will be used as the filename with a ".icc" extension.
        """
        stream = self._get_stream(stream_or_filename, ".icc")

        link = ICCProfile()
        link.connectionColorSpace = b"RGB"
        link.profileClass = b"link"
        link.tags.desc = TextDescriptionType()
        link.tags.desc.ASCII = os.path.splitext(os.path.basename(stream.name))[0]
        link.tags.cprt = TextType(b"text\0\0\0\0No copyright", b"cprt")

        input_grid_steps = (
            2 ** self.inputBitDepth[0]
        )  # Assume equal bitdepth for R, G, B
        # madVR 3D LUTs are 256^3, but ICC LUT16Type only supports up to
        # 255^3. As madVR 3D LUTs use video levels encoding, we simply skip
        # the first cLUT entry in each dimension and fix the offset by
        # scaling the input/output shaper curves. That way, only level 1 of
        # 255 will be affected (with black at 16 and white at 235),
        # which isn't used in actual video content.
        clut_grid_steps = 255 if input_grid_steps > 255 else input_grid_steps
        # Filling a 255^3 list is VERY memory intensive in Python, so we 'fake'
        # the LUT16Type cLUT and only use tag data of offsets/sizes and shaper
        # curves while writing the raw cLUT data directly without going through
        # decoding/re-encoding roundtrip
        a2b0 = LUT16Type()
        a2b0.matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        a2b0.input = []
        for _ in range(3):
            a2b0.input.append([])
            for j in range(4096):
                a2b0.input[-1].append(
                    min(max(j / 4095.0 * (256 / 255.0) - (256 / 255.0 - 1), 0), 1)
                    * 65535
                )
        input_bytes = len(a2b0.input) * len(a2b0.input[0]) * 2
        a2b0.clut = [[[0] * 3 for i in range(clut_grid_steps)]]  # Fake cLUT
        a2b0.output = []
        for _ in range(3):
            a2b0.output.append([])
            for j in range(4096):
                a2b0.output[-1].append(
                    min(max(j / 4095.0 * (256 / 255.0), 0), 1) * 65535
                )
        output_bytes = len(a2b0.output) * len(a2b0.output[0]) * 2
        tag_data = a2b0.tagData[: 52 + input_bytes]  # Exclude cLUT and output curves

        # Write actual cLUT
        # XXX Currently only 16 bit RGB data is supported
        samples_per_pixel = 3  # RGB
        bytes_per_sample = self.outputBitDepth / 8
        bytes_per_pixel = samples_per_pixel * bytes_per_sample
        io = BytesIO(tag_data)
        io.seek(0, 2)  # Position cursor at end
        i = 0
        for r in range(input_grid_steps):
            if not r:
                i += input_grid_steps * input_grid_steps
                continue
            for g in range(input_grid_steps):
                if not g:
                    i += input_grid_steps
                    continue
                for b in range(input_grid_steps):
                    if not b:
                        i += 1
                        continue
                    index = i * samples_per_pixel * bytes_per_sample
                    bgr = self.LUTDATA[index : index + bytes_per_pixel]
                    rgb = bgr[::-1]  # BGR little-endian to RGB big-endian byte order
                    io.write(rgb)
                    i += 1
        io.write(a2b0.tagData[-output_bytes:])  # Append output curves
        io.seek(0)
        link.tags.A2B0 = ICCProfileTag(io.read(), "A2B0")

        link.write(stream)

        if isinstance(stream_or_filename, str):
            stream.close()

    def write_tiff(self, stream_or_filename: None | str | BinaryIO = None) -> None:
        """Write 3D LUT to TIFF file.

        Args:
            stream_or_filename (None | str | BinaryIO, optional): The file path
                or a binary stream to write the TIFF data to. If None, uses the
                filename from the instance. If a string is provided, it will be
                used as the filename with a ".tif" extension.
        """
        stream = self._get_stream(stream_or_filename, ".tif")

        # Write image data
        # XXX Currently only 8 or 16 bit RGB data is supported
        samples_per_pixel = 3  # RGB
        bytes_per_sample = self.outputBitDepth / 8
        bytes_per_pixel = samples_per_pixel * bytes_per_sample
        w = 2 ** self.inputBitDepth[0]  # Assume equal bitdepth for R, G, B
        h = w * w
        stream.write(tiff_get_header(w, h, samples_per_pixel, self.outputBitDepth))
        entries = self.lutUncompressedSize / samples_per_pixel / bytes_per_sample
        for i in range(entries):
            index = i * samples_per_pixel * bytes_per_sample
            bgr = self.LUTDATA[index : index + bytes_per_pixel]
            rgb = bgr[::-1]  # BGR little-endian to RGB big-endian byte order
            stream.write(rgb)

        if isinstance(stream_or_filename, str):
            stream.close()


class MadTPGBase:
    """Generic pattern generator compatibility layer."""

    def wait(self) -> None:
        """Wait for madTPG to be ready."""
        self.connect(method2=CM_StartLocalInstance)

    def disconnect_client(self) -> None:
        """Disconnect the client from madTPG."""
        self.disconnect()

    def send(
        self,
        rgb: tuple[float, float, float] = (0, 0, 0),
        bgrgb: tuple[float, float, float] = (0, 0, 0),
        bits: None | int = None,
        use_video_levels: None | bool = None,
        x: int = 0,
        y: int = 0,
        w: int = 1,
        h: int = 1,
    ) -> None:
        """Send RGB values to madTPG.

        Args:
            rgb (tuple[float, float, float], optional): RGB values to display,
                each in the range 0-255.
            bgrgb (tuple[float, float, float], optional): BGR values to
                display, each in the range 0-255.
            bits (None | int, optional): Bit depth of the RGB values. Defaults to
                None, which means the default bit depth will be used.
            use_video_levels (None | bool): Whether to use video levels.
                Defaults to None.
            x (int, optional): X position on screen to display the pattern.
            y (int, optional): Y position on screen to display the pattern.
            w (int, optional): Width of the pattern area.
            h (int, optional): Height of the pattern area.
        """
        cfg = self.get_pattern_config()
        if cfg:
            self.set_pattern_config(
                round((w + h) / 2.0 * 100),
                round(sum(bgrgb) / 3.0 * 100),
                cfg[2],
                cfg[3],
            )
        self.show_rgb(*rgb + bgrgb)


class MadTPG(MadTPGBase):
    """Minimal madTPG controller class."""

    def __init__(self) -> None:
        MadTPGBase.__init__(self)
        self._connection_callbacks = []

        # We only expose stuff we might actually use.
        # Also, as the HDR 3D LUT install API of madVR is relatively recent
        # (September 2017), we do not require it.

        # Find madHcNet32.dll
        clsid = "{E1A8B82A-32CE-4B0D-BE0D-AA68C772E423}"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\InprocServer32"
            )
            value, valuetype = winreg.QueryValueEx(key, "")
        except Exception as e:
            raise RuntimeError(lang.getstr("madvr.not_found")) from e
        bits = 64 if platform.architecture()[0] == "64bit" else 32
        self.dllpath = os.path.join(os.path.split(value)[0], f"madHcNet{bits}.dll")
        if not value or not os.path.isfile(self.dllpath):
            raise OSError(lang.getstr("not_found", self.dllpath))
        handle = win32api.LoadLibrary(self.dllpath)
        self.mad = ctypes.WinDLL(self.dllpath, handle=handle)

        try:
            # Set expected return value types
            for methodname in _METHOD_NAMES + _AUTONET_METHOD_NAMES:
                if methodname == "AddConnectionCallback":
                    continue
                prefix = "AutoNet" if methodname in _AUTONET_METHOD_NAMES else "madVR"
                method = getattr(self.mad, prefix + "_" + methodname, None)
                if not method and not methodname.startswith("LoadHdr3dlut"):
                    raise AttributeError(prefix + "_" + methodname)
                method.restype = ctypes.c_bool

            # Set expected argument types
            self.mad.madVR_ShowRGB.argtypes = [ctypes.c_double] * 3
            self.mad.madVR_ShowRGBEx.argtypes = [ctypes.c_double] * 6
            if hasattr(self.mad, "madVR_LoadHdr3dlutFile"):
                self.mad.madVR_LoadHdr3dlutFile.argtypes = [
                    ctypes.wintypes.LPWSTR,
                    ctypes.wintypes.BOOL,
                    ctypes.c_int,
                    ctypes.c_bool,
                ]
        except AttributeError as e:
            raise RuntimeError(
                lang.getstr(
                    "madhcnet.outdated",
                    tuple(reversed(os.path.split(self.dllpath))) + MIN_VERSION,
                )
            ) from e

    def __del__(self) -> None:
        """Destructor to clean up madTPG instance."""
        if hasattr(self, "mad"):
            self.disconnect()

    def __getattr__(self, name: str) -> Callable:
        """Handle madVR method calls.

        This is a generic method to handle madVR method calls. It allows
        dynamic access to madVR methods based on their names. The method
        names are expected to be in a pythonic format (e.g., 'disable_3dlut'
        instead of 'Disable3dlut'). The method converts the pythonic name
        to the appropriate CamelCase format used by madVR and checks if
        the method exists. If it does, it returns the method for further
        invocation. If the method does not exist, it raises an AttributeError.
        This approach avoids the need to write individual method wrappers
        for each madVR method, making the code cleaner and more maintainable.

        Args:
            name (str): The name of the madVR method to be called, in a
                pythonic format (e.g., 'disable_3dlut').

        Raises:
            AttributeError: If the method name does not correspond to a
                valid madVR method.

        Returns:
            Callable: The madVR method corresponding to the provided name.
        """
        # Instead of writing individual method wrappers, we use Python's magic
        # to handle this for us. Note that we're sticking to pythonic method
        # names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

        # Convert from pythonic method name to CamelCase
        methodname = "".join(part.capitalize() for part in name.split("_"))

        # Check if this is a madVR method we support
        if methodname not in _METHOD_NAMES + _AUTONET_METHOD_NAMES:
            raise AttributeError(
                f"{self.__class__.__name__!r} object has no attribute {name!r}"
            )

        # Return the method
        prefix = "AutoNet" if methodname in _AUTONET_METHOD_NAMES else "madVR"
        return getattr(self.mad, f"{prefix}_{methodname}")

    def add_connection_callback(
        self,
        callback: Callable,
        param: Any,  # noqa: ANN401
        component: str,
    ) -> None:
        """Handle callbacks for added/closed connections to playback components.

        Leave "component" empty to get notification about all components.

        The callback function has to take eight arguments:
        param, connection, ip, pid, module, component, instance, is_new_instance

        Args:
            callback (Callable): The callback function to be called when a
                connection is added or closed.
            param (Any): Additional parameter to be passed to the callback.
            component (str): The name of the component to monitor for
                connections.
        """
        callback = CALLBACK(callback)
        self.mad.AutoNet_AddConnectionCallback(callback, param, component)
        self._connection_callbacks.append(callback)

    def connect(
        self,
        method1: int = CM_ConnectToLocalInstance,
        timeout1: int = 1000,
        method2: int = CM_ConnectToLanInstance,
        timeout2: int = 3000,
        method3: int = CM_ShowListDialog,
        timeout3: int = 0,
        method4: int = CM_Fail,
        timeout4: int = 0,
        parentwindow: None | int = None,
    ) -> bool:
        """Find, select or launch a madTPG instance and connect to it.

        Args:
            method1 (int): Connection method for the first attempt.
            timeout1 (int): Timeout in milliseconds for the first attempt.
            method2 (int): Connection method for the second attempt.
            timeout2 (int): Timeout in milliseconds for the second attempt.
            method3 (int): Connection method for the third attempt.
            timeout3 (int): Timeout in milliseconds for the third attempt.
            method4 (int): Connection method for the fourth attempt.
            timeout4 (int): Timeout in milliseconds for the fourth attempt.
            parentwindow (None | int): Parent window handle for dialogs.

        Returns:
            bool: True if the connection was successful, False otherwise.
        """
        return self.mad.madVR_ConnectEx(
            method1,
            timeout1,
            method2,
            timeout2,
            method3,
            timeout3,
            method4,
            timeout4,
            parentwindow,
        )

    def get_black_and_white_level(self) -> bool | tuple[int, int]:
        """Return madVR output level setup.

        Returns:
            bool | tuple[int, int]: A tuple containing the black and white
                levels. If the call fails, returns False.
        """
        blacklvl, whitelvl = ctypes.c_long(), ctypes.c_long()
        result = self.mad.madVR_GetBlackAndWhiteLevel(
            *[ctypes.byref(v) for v in (blacklvl, whitelvl)]
        )
        return result and (blacklvl.value, whitelvl.value)

    def get_device_gamma_ramp(self) -> bool | ctypes.Array:
        """Call the win32 API 'GetDeviceGammaRamp'.

        Returns:
            bool | ctypes.Array: A ctypes array containing the gamma ramp
                values for red, green, and blue channels. Each channel has 256
                entries. If the call fails, returns False.
        """
        ramp = ((ctypes.c_ushort * 256) * 3)()
        result = self.mad.madVR_GetDeviceGammaRamp(ramp)
        return result and ramp

    def get_pattern_config(self) -> bool | tuple[int, int, int, int]:
        """Return the pattern config as 4-tuple.

        Pattern area in percent        1-100
        Background level in percent    0-100
        Background mode                0 = constant gray
                                       1 = APL - gamma light
                                       2 = APL - linear light
        Black border width in pixels   0-100

        Returns:
            bool | tuple[int, int, int, int]: A tuple containing the pattern
                area, background level, background mode, and black border
                width. If the call fails, returns False.
        """
        area, bglvl, bgmode, border = [ctypes.c_long() for i in range(4)]
        result = self.mad.madVR_GetPatternConfig(
            *[ctypes.byref(v) for v in (area, bglvl, bgmode, border)]
        )
        return result and (area.value, bglvl.value, bgmode.value, border.value)

    def get_selected_3dlut(self) -> bool | int:
        """Return the currently selected 3D LUT ID.

        Returns:
            bool | int: The ID of the selected 3D LUT, or None if no LUT is
                selected.
        """
        thr3dlut = ctypes.c_ulong()
        result = self.mad.madVR_GetSelected3dlut(ctypes.byref(thr3dlut))
        return result and thr3dlut.value

    def get_version(self) -> bool | tuple[str, str, str, str]:
        """Return the madVR version as 4-tuple.

        Returns:
            bool | tuple[str, str, str, str]: The madVR version as a tuple of
                four strings representing the major, minor, patch, and build
                numbers.
        """
        version = ctypes.c_ulong()
        result = self.mad.madVR_GetVersion(ctypes.byref(version))
        return result and tuple(c for c in struct.pack(">I", version.value))

    def show_rgb(
        self,
        r: float,
        g: float,
        b: float,
        bgr: None | float = None,
        bgg: None | float = None,
        bgb: None | float = None,
    ) -> bool:
        """Show a specific RGB color test pattern.

        Args:
            r (float): Red component in the range 0.0-255.0.
            g (float): Green component in the range 0.0-255.0.
            b (float): Blue component in the range 0.0-255.0.
            bgr (None | float, optional): Red component for the background
                color.
            bgg (None | float, optional): Green component for the background
                color.
            bgb (None | float, optional): Blue component for the background
                color.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        if None not in (bgr, bgg, bgb):
            return self.mad.madVR_ShowRGBEx(r, g, b, bgr, bgg, bgb)
        return self.mad.madVR_ShowRGB(r, g, b)

    @property
    def uri(self) -> str:
        """Return the URI of the madTPG instance.

        Returns:
            str: The URI of the madTPG instance, which is the path to the DLL.
        """
        return self.dllpath


class MadTPGNet(MadTPGBase):
    """Implementation of madVR network protocol in pure python.

    Wireshark filter to help ananlyze traffic:

        (tcp.dstport != 1900 and tcp.dstport != 443) or
        (udp.dstport != 1900 and udp.dstport != 137 and
        udp.dstport != 138 and udp.dstport != 5355 and
        udp.dstport != 547 and udp.dstport != 10111)
    """

    def __init__(self) -> None:
        MadTPGBase.__init__(self)
        self._cast_sockets = {}
        self._casts = []
        self._client_sockets = {}
        self._commandno = 0
        self._commands = {}
        self._host = get_network_addr()
        self._incoming = {}
        self._ips = [i[4][0] for i in socket.getaddrinfo(self._host, None)]
        self._pid = 0
        self._reset()
        self._server_sockets = {}
        self._threads = []
        # self.broadcast_ports = (39568, 41513, 45817, 48591, 48912)
        self.broadcast_ports = (37018, 10658, 63922, 53181, 4287)
        self.clients = {}
        self.debug = 0
        self.listening = False
        # self.multicast_ports = (34761, )
        self.multicast_ports = (51591,)
        self._event_handlers = {
            "on_client_added": [],
            "on_client_confirmed": [],
            "on_client_removed": [],
            "on_client_updated": [],
        }
        # self.server_ports = (37612, 43219, 47815, 48291, 48717)
        self.server_ports = (60562, 51130, 54184, 41916, 19902)
        ip = self._host.split(".")
        ip.pop()
        ip.append("255")
        self.broadcast_ip = ".".join(ip)
        self.multicast_ip = "235.117.220.191"

    def listen(self) -> None:
        """Start listening for incoming connections and broadcasts."""
        self.listening = True
        # Connection listen sockets
        for port in self.server_ports:
            if ("", port) in self._server_sockets:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(0)
            try:
                sock.bind(("", port))
                sock.listen(1)
                thread = threading.Thread(
                    target=self._conn_accept_handler,
                    name=f"madVR.ConnectionHandler[{port}]",
                    args=(sock, "", port),
                )
                self._threads.append(thread)
                thread.start()
            except OSError as exception:
                safe_print(f"MadTPG_Net: TCP Port {port}: {exception}")
        # Broadcast listen sockets
        for port in self.broadcast_ports:
            if (self.broadcast_ip, port) in self._cast_sockets:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0)
            try:
                sock.bind(("", port))
                thread = threading.Thread(
                    target=self._cast_receive_handler,
                    name=f"madVR.BroadcastHandler[{self.broadcast_ip}:{port}]",
                    args=(sock, self.broadcast_ip, port),
                )
                self._threads.append(thread)
                thread.start()
            except OSError as exception:
                safe_print(f"MadTPG_Net: UDP Port {port}: {exception}")
        # Multicast listen socket
        for port in self.multicast_ports:
            if (self.multicast_ip, port) in self._cast_sockets:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                struct.pack(
                    "4sl", socket.inet_aton(self.multicast_ip), socket.INADDR_ANY
                ),
            )
            sock.settimeout(0)
            try:
                sock.bind(("", port))
                thread = threading.Thread(
                    target=self._cast_receive_handler,
                    name=f"madVR.MulticastHandler[{self.multicast_ip}:{port}]",
                    args=(sock, self.multicast_ip, port),
                )
                self._threads.append(thread)
                thread.start()
            except OSError as exception:
                safe_print(f"MadTPG_Net: UDP Port {port}: {exception}")

    def bind(self, event_name: str, handler: Callable) -> None:
        """Bind a handler to an event.

        Args:
            event_name (str): The name of the event to bind to.
            handler (Callable): The handler function to bind to the event.
        """
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def unbind(
        self, event_name: str, handler: None | Callable = None
    ) -> None | Callable:
        """Unbind (remove) a handler from an event.

        Args:
            event_name (str): The name of the event to unbind from.
            handler (None | Callable, optional): The handler to remove.
                If None, all handlers for the event will be removed.

        Returns:
            None | Callable: If handler is specified and found, it is returned.
                If handler is None, all handlers for the event are removed.
                If the event has no handlers, None is returned.
        """
        if event_name not in self._event_handlers:
            return None

        if handler in self._event_handlers[event_name]:
            self._event_handlers[event_name].remove(handler)
            return handler

        return self._event_handlers.pop(event_name)

    def _dispatch_event(self, event_name: str, event_data: None | Any = None) -> None:  # noqa: ANN401
        """Dispatch events.

        Args:
            event_name (str): The name of the event to dispatch.
            event_data (None | Any, optional): Data associated with the event.
                Defaults to None.
        """
        if self.debug:
            safe_print("MadTPG_Net: Dispatching", event_name)
        for handler in self._event_handlers.get(event_name, []):
            handler(event_data)

    def _reset(self) -> None:
        self._client_socket = None

    def _conn_accept_handler(self, sock: socket.socket, host: str, port: int) -> None:
        """Handle incoming connections on a TCP socket.

        Args:
            sock (socket.socket): The socket to accept connections on.
            host (str): The host address to bind to.
            port (int): The port to bind to.
        """
        if self.debug:
            safe_print("MadTPG_Net: Entering incoming connection thread for port", port)
        self._server_sockets[(host, port)] = sock
        while getattr(self, "listening", False):
            try:
                # Wait for connection
                conn, addr = sock.accept()
            except socket.timeout as exception:
                # Should never happen for non-blocking socket
                safe_print(
                    f"MadTPG_Net: In incoming connection thread for port {port}:",
                    exception,
                )
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                safe_print(
                    "MadTPG_Net: Exception in incoming connection "
                    f"thread for {addr[0]}:{addr[1]}:",
                    exception,
                )
                break
            conn.settimeout(0)
            with _LOCK:
                if self.debug:
                    socket_name = conn.getsockname()
                    safe_print(
                        "MadTPG_Net: Incoming connection from "
                        f"{addr[0]}:{addr[1]} to {socket_name[0]}:{socket_name[1]}"
                    )
                if addr in self._client_sockets:
                    if self.debug:
                        socket_name = conn.getsockname()
                        safe_print(
                            "MadTPG_Net: Already connected from "
                            f"{addr[0]}:{addr[1]} to {socket_name[0]}:{socket_name[1]}"
                        )
                    self._shutdown(conn, addr)
                else:
                    self._client_sockets[addr] = conn
                    thread = threading.Thread(
                        target=self._receive_handler,
                        name=f"madVR.Receiver[{addr[0]}:{addr[1]}]",
                        args=(
                            addr,
                            conn,
                        ),
                    )
                    self._threads.append(thread)
                    thread.start()
        self._server_sockets.pop((host, port))
        self._shutdown(sock, (host, port))
        if self.debug:
            safe_print("MadTPG_Net: Exiting incoming connection thread for port", port)

    def _receive_handler(self, addr: tuple, conn: socket.socket) -> None:
        """Handle incoming messages from a client connection.

        Args:
            addr (tuple): The address of the client (IP, port).
            conn (socket.socket): The socket connection to the client.
        """
        if self.debug:
            safe_print(f"MadTPG_Net: Entering receiver thread for {addr[0]}:{addr[1]}")
        self._incoming[addr] = []
        hello = self._hello(conn)
        blob = b""
        send_bye = True
        while (
            hello and addr in self._client_sockets and getattr(self, "listening", False)
        ):
            # Wait for incoming message
            try:
                incoming = conn.recv(4096)
            except socket.timeout as exception:
                # Should never happen for non-blocking socket
                safe_print(
                    f"MadTPG_Net: In receiver thread for {addr[0]}:{addr[1]}:",
                    exception,
                )
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.001)
                    continue
                if exception.errno not in (errno.EBADF, errno.ECONNRESET) or self.debug:
                    safe_print(
                        f"MadTPG_Net: In receiver thread for {addr[0]}:{addr[1]}:",
                        exception,
                    )
                send_bye = False
                break
            else:
                send_bye, break_early, blob = self._process_client_message(
                    addr, conn, incoming, send_bye, blob
                )
                if break_early:
                    break
        with _LOCK:
            self._remove_client(
                addr, send_bye=addr in self._client_sockets and send_bye
            )
            self._incoming.pop(addr)
        if self.debug:
            safe_print(
                "MadTPG_Net: Exiting receiver thread for {}:{}".format(*addr[:2])
            )

    def _process_client_message(
        self,
        addr: tuple,
        conn: socket.socket,
        incoming: bytes,
        send_bye: bool,
        blob: bytes,
    ) -> tuple[bool, bool, bytes]:
        """Process incoming message from a client.

        Args:
            addr (tuple): The address of the client (IP, port).
            conn (socket.socket): The socket connection to the client.
            incoming (bytes): The incoming data from the client.
            send_bye (bool): Whether to send a "bye" message on disconnection.
            blob (bytes): The accumulated data blob for processing.

        Returns:
            tuple: The updated send_bye flag, whether to break early from the
                processing loop, and the unconsumed bytes for the next receive.
        """
        with _LOCK:
            if not incoming:
                # Connection broken
                if self.debug:
                    safe_print(
                        f"MadTPG_Net: Client {addr[0]}:{addr[1]} stopped sending"
                    )
                send_bye = False
                return send_bye, True, blob
            blob += incoming
            if self.debug:
                safe_print("MadTPG_Net: Received from {}:{}:".format(*addr[:2]))
            while blob and addr in self._client_sockets:
                try:
                    record, blob = self._parse(blob)
                except ValueError as exception:
                    safe_print("MadTPG_Net:", exception)
                    # Invalid, discard
                    blob = b""
                else:
                    if record is None:
                        # Need more data
                        break
                    try:
                        self._process(record, conn)
                    except OSError as exception:
                        safe_print("MadTPG_Net:", exception)
        return send_bye, False, blob

    def _remove_client(self, addr: tuple, send_bye: bool = True) -> None:
        """Remove client from list of connected clients.

        Args:
            addr (tuple): The address of the client to be removed.
            send_bye (bool, optional): Whether to send a "bye" message before
                removing. Defaults to True.
        """
        if addr not in self._client_sockets:
            return
        conn = self._client_sockets.pop(addr)
        if send_bye:
            self._send(
                conn,
                "bye",
                component=self.clients.get(addr, {}).get("component", b""),
            )
        if addr in self.clients:
            client = self.clients.pop(addr)
            if self.debug:
                safe_print(f"MadTPG_Net: Removed client {addr[0]}:{addr[1]}")
            self._dispatch_event("on_client_removed", (addr, client))
        if self._client_socket and self._client_socket == conn:
            self._reset()
        self._shutdown(conn, addr)

    def _cast_receive_handler(
        self,
        sock: socket.socket,
        host: str,
        port: int,
    ) -> None:
        """Handle incoming broadcasts and multicasts.

        Args:
            sock (socket.socket): The socket to listen for broadcasts or multicasts.
            host (str): The host address for the broadcast or multicast.
            port (int): The port number for the broadcast or multicast.
        """
        if host == self.broadcast_ip:
            cast = "broadcast"
        elif host == self.multicast_ip:
            cast = "multicast"
        else:
            cast = "unknown"
        if self.debug:
            safe_print(f"MadTPG_Net: Entering receiver thread for {cast} port {port}")
        self._cast_sockets[(host, port)] = sock
        while getattr(self, "listening", False):
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout as exception:
                safe_print(
                    f"MadTPG_Net: In receiver thread for {cast} port {port}:",
                    exception,
                )
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                if exception.errno != errno.ECONNRESET or self.debug:
                    safe_print(
                        f"MadTPG_Net: In receiver thread for {cast} port {port}:",
                        exception,
                    )
                break
            else:
                self._process_incoming_cast(cast, data, addr)
        self._cast_sockets.pop((host, port))
        self._shutdown(sock, (host, port))
        if self.debug:
            safe_print(f"MadTPG_Net: Exiting {cast} receiver thread for port {port}")

    def _process_incoming_cast(self, cast: str, data: bytes, addr: tuple) -> None:
        """Process incoming broadcast or multicast message.

        Args:
            cast (str): Type of the cast ("broadcast" or "multicast").
            data (bytes): The received data.
            addr (tuple): The address of the sender (IP, port).
        """
        with _LOCK:
            if self.debug:
                safe_print(
                    f"MadTPG_Net: Received {cast} from {addr[0]}:{addr[1]}: {data!r}"
                )
            if addr not in self._casts:
                for c_port in self.server_ports:
                    if (addr[0], c_port) in self._client_sockets:
                        if self.debug:
                            safe_print(
                                f"MadTPG_Net: Already connected to {addr[0]}:{c_port}"
                            )
                    elif ("", c_port) in self._server_sockets and addr[0] in self._ips:
                        if self.debug:
                            safe_print(
                                f"MadTPG_Net: Don't connect to self {addr[0]}:{c_port}"
                            )
                    else:
                        conn = self._get_client_socket(addr[0], c_port)
                        threading.Thread(
                            target=self._connect,
                            name=f"madVR.ConnectToInstance[{addr[0]}:{c_port}]",
                            args=(conn, addr[0], c_port),
                        ).start()
            else:
                self._casts.remove(addr)
                if self.debug:
                    safe_print(
                        f"MadTPG_Net: Ignoring own {cast} from {addr[0]}:{addr[1]}"
                    )

    def __del__(self) -> None:
        """Clean up resources on deletion."""
        self.shutdown()

    def _shutdown(self, sock: socket.socket, addr: tuple) -> None:
        """Shutdown and close the socket.

        Args:
            sock (socket.socket): The socket to be shut down and closed.
            addr (tuple): The address of the socket, used for logging.
        """
        try:
            # Will fail if the socket isn't connected, i.e. if there
            # was an error during the call to connect()
            sock.shutdown(socket.SHUT_RDWR)
        except OSError as exception:
            if exception.errno != errno.ENOTCONN:
                safe_print(
                    f"MadTPG_Net: SHUT_RDWR for {addr[0]}:{addr[1]} failed:",
                    exception,
                )
        sock.close()

    def shutdown(self) -> None:
        """Shutdown the madTPG network connection."""
        self.disconnect()
        self.listening = False
        while self._threads:
            thread = self._threads.pop()
            if thread.is_alive():
                thread.join()

    def __getattr__(self, name: str) -> MadTPGNetSender:
        """Get attribute from madVR DLL.

        Args:
            name (str): Name of the method to call.

        Raises:
            AttributeError: If the method name is not found in the madVR DLL.

        Returns:
            MadTPGNetSender: An instance of MadTPGNetSender with the method
                name set to the specified method.
        """
        # Instead of writing individual method wrappers, we use Python's magic
        # to handle this for us. Note that we're sticking to pythonic method
        # names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

        # Convert from pythonic method name to CamelCase
        methodname = "".join(part.capitalize() for part in name.split("_"))

        if methodname == "ShowRgb":
            methodname = "ShowRGB"

        # Check if this is a madVR method we support
        if methodname not in _METHOD_NAMES:
            raise AttributeError(
                f"{self.__class__.__name__!r} object has no attribute {name!r}"
            )

        # Call the method and return the result
        return MadTPGNetSender(self, self._client_socket, methodname)

    def announce(self) -> None:
        """Anounce ourselves."""
        for port in self.multicast_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
            sock.settimeout(1)
            sock.connect((self.multicast_ip, port))
            addr = sock.getsockname()
            self._casts.append(addr)
            if self.debug:
                safe_print(
                    f"MadTPG_Net: Sending multicast from {addr[0]}:{addr[1]} "
                    f"to port {port}"
                )
            sock.sendall(struct.pack("<i", 0))
            self._shutdown(sock, (self.multicast_ip, port))
        for port in self.broadcast_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1)
            sock.connect((self.broadcast_ip, port))
            addr = sock.getsockname()
            self._casts.append(addr)
            if self.debug:
                safe_print(
                    f"MadTPG_Net: Sending broadcast from {addr[0]}:{addr[1]} "
                    f"to port {port}"
                )
            sock.sendall(struct.pack("<i", 0))
            self._shutdown(sock, (self.broadcast_ip, port))

    def connect(
        self,
        method1: int = CM_ConnectToLanInstance,
        timeout1: int = 4000,
        method2: int = CM_ShowListDialog,
        timeout2: int = 0,
        method3: int = CM_Fail,
        timeout3: int = 0,
        method4: int = CM_Fail,
        timeout4: int = 0,
        parentwindow: None | int = None,
    ) -> bool:
        """Find or select a madTPG instance on the network and connect to it.

        Args:
            method1 (int, optional): The first connection method to try.
                Defaults to CM_ConnectToLanInstance.
            timeout1 (int, optional): Timeout for the first connection method
                in milliseconds. Defaults to 4000.
            method2 (int, optional): The second connection method to try.
                Defaults to CM_ShowListDialog.
            timeout2 (int, optional): Timeout for the second connection method
                in milliseconds. Defaults to 0.
            method3 (int, optional): The third connection method to try.
                Defaults to CM_Fail.
            timeout3 (int, optional): Timeout for the third connection method
                in milliseconds. Defaults to 0.
            method4 (int, optional): The fourth connection method to try.
                Defaults to CM_Fail.
            timeout4 (int, optional): Timeout for the fourth connection method
                in milliseconds. Defaults to 0.
            parentwindow (None | int): The parent window for any dialogs that
                may be shown.

        Returns:
            bool: True if the connection was successful, False otherwise.
        """
        listened = self.listening
        for method, timeout in [
            (method1, timeout1),
            (method2, timeout2),
            (method3, timeout3),
            (method4, timeout4),
        ]:
            timeout = timeout / 1000.0
            if method in (CM_ConnectToLanInstance, CM_ShowListDialog):
                if not self._cast_sockets and not listened:
                    self.listen()
                    listened = True
                    # Give a little time for the user to acknowledge any
                    # OS firewall prompts
                    sleep(3)
                if method == CM_ShowListDialog:
                    # TODO: Implement
                    pass
                elif self.listening:
                    # Re-use existing connection
                    if self._wait_for_client(None, 0.001):
                        return True
                    # Otherwise, announce ourselves
                    self.announce()
                    if self._wait_for_client(None, timeout - 0.001):
                        return True
            elif method == CM_ShowIpAddrDialog:
                # TODO: Implement
                pass
        return False

    def connect_to_ip(self, ip: str, timeout: int = 1000) -> bool:
        """Connect to madTPG running under a known IP address.

        Args:
            ip (str): The IP address of the madTPG instance.
            timeout (int, optional): Timeout for the connection attempt in
                milliseconds. Defaults to 1000.

        Returns:
            bool: True if the connection was successful, False otherwise.
        """
        ip = socket.gethostbyname(ip)
        for port in self.server_ports:
            conn = self._get_client_socket(ip, port)
            threading.Thread(
                target=self._connect,
                name=f"madVR.ConnectToInstance[{ip}:{port}]",
                args=(conn, ip, port, timeout / 1000.0),
            ).start()
        return self._wait_for_client((ip, port), timeout / 1000.0)

    def _get_client_socket(
        self, host: str, port: int, timeout: float = 1
    ) -> socket.socket:
        """Return a new or existing client socket.

        Args:
            host (str): The host IP address.
            port (int): The port number to connect to.
            timeout (float): Timeout for the connection attempt in seconds.

        Returns:
            socket.socket: The client socket for the specified host and port.
        """
        if (host, port) in self._client_sockets:
            return self._client_sockets[(host, port)]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        self._client_sockets[(host, port)] = sock
        return sock

    def _connect(
        self, sock: socket.socket, host: str, port: int, timeout: float = 1
    ) -> None:
        """Connect to IP:PORT, return socket.

        Args:
            sock (socket.socket): The socket to connect.
            host (str): The host IP address.
            port (int): The port number to connect to.
            timeout (float): Timeout for the connection attempt in seconds.

        Raises:
            OSError: If the connection fails.
        """
        if self.debug:
            safe_print(f"MadTPG_Net: Connecting to {host}:{port}...")
        try:
            sock.connect((host, port))
        except OSError as exception:
            if self.debug:
                safe_print(
                    f"MadTPG_Net: Connecting to {host}:{port} failed:", exception
                )
            with _LOCK:
                self._remove_client((host, port), False)
        else:
            if self.debug:
                safe_print(f"MadTPG_Net: Connected to {host}:{port}")
            sock.settimeout(0)
            thread = threading.Thread(
                target=self._receive_handler,
                name=f"madVR.Receiver[{host}:{port}]",
                args=(
                    (host, port),
                    sock,
                ),
            )
            self._threads.append(thread)
            thread.start()

    def disconnect(self, stop: bool = True) -> bool:
        """Disconnect from madTPG instance.

        Args:
            stop (bool): If True, send 'StopTestPattern' command to madTPG.
                Defaults to True.

        Returns:
            bool: True if the disconnect was successful, False otherwise.
        """
        returnvalue = False
        conn = self._client_socket
        if conn:
            returnvalue = True
            if stop:
                returnvalue = self._send(conn, "StopTestPattern")
        self._reset()
        return returnvalue

    def _process(self, record: dict, conn: socket.socket) -> None:
        """Process madVR packet.

        Args:
            record (dict): The parsed record from the madVR packet.
            conn (socket.socket): The socket connection from which the packet
                was received.
        """
        command = record["command"]
        if command not in ("bye", "confirm", "hello", "reply"):
            # Ignore
            return
        addr = conn.getpeername()
        commandno = record["commandNo"]
        component = record["component"]
        params = record["params"]
        client = {}
        client["processId"] = record["processId"]
        client["module"] = record["module"]
        client["component"] = component
        client["instance"] = record["instance"]
        if command == "reply":
            if params == b"+":
                params = True
            elif params == b"-":
                params = False
        elif command == "confirm":
            if addr not in self.clients:
                self.clients[addr] = client
                self._dispatch_event("on_client_added", (addr, self.clients[addr]))
            self.clients[addr]["confirmed"] = True
            self._dispatch_event("on_client_confirmed", (addr, self.clients[addr]))
        elif command == "hello":
            is_duplicate_connection = self._process_new_client(
                conn, addr, params, client
            )
            if is_duplicate_connection:
                # Duplicate connection, ignore
                return
        elif command == "bye":
            if self.debug:
                safe_print(f"MadTPG_Net: Client {addr[0]}:{addr[1]} disconnected")
            self._remove_client(addr)
        self._incoming[addr].append((commandno, command, params, component))

    def _process_new_client(
        self,
        conn: socket.socket,
        addr: tuple,
        params: str,
        client: dict,
    ) -> bool:
        """Process new client connection.

        Args:
            conn (socket.socket): The socket connection from which the packet
                was received.
            addr (tuple): The address of the client (IP, port).
            params (str): The parameters from the 'hello' packet.
            client (dict): The client information extracted from the packet.

        Returns:
            bool: True if the connection is a duplicate and should be ignored,
                False otherwise.
        """
        client.update(params)
        if addr not in self.clients:
            self.clients[addr] = client
            if self._is_master(conn):
                # Prevent duplicate connections
                for c_addr in self.clients:
                    c_client = self.clients[c_addr]
                    if (
                        c_client.get("confirmed")
                        and c_client["processId"] == client["processId"]
                        and c_client["module"] == client["module"]
                    ):
                        if self.debug:
                            safe_print(
                                "MadTPG_Net: Preventing duplicate connection "
                                f"{addr[0]}:{addr[1]}"
                            )
                        self._remove_client(addr, False)
                        return True
            self._dispatch_event("on_client_added", (addr, client))
        else:
            client_copy = self.clients[addr].copy()
            self.clients[addr].update(client)
            if self.clients[addr] != client_copy:
                self._dispatch_event("on_client_updated", (addr, self.clients[addr]))
        if (
            not self.clients[addr].get("confirmed")
            and self._is_master(conn)
            and self._send(conn, "confirm", component=b"")
        ):
            self._sent_confirm_packet_for_master(addr, client)
        return False

    def _sent_confirm_packet_for_master(self, addr: tuple, client: dict) -> None:
        """Handle actions after sending confirm packet as master.

        Args:
            addr (tuple): The address of the client (IP, port).
            client (dict): The client information extracted from the packet.
        """
        # We are master, sent confirm packet
        self.clients[addr]["confirmed"] = True
        self._dispatch_event("on_client_confirmed", (addr, self.clients[addr]))
        # Close duplicate connections
        for c_addr in self.clients:
            c_client = self.clients[c_addr]
            if (
                c_addr != addr
                and c_client["processId"] == client["processId"]
                and c_client["module"] == client["module"]
            ):
                if self.debug:
                    safe_print(
                        "MadTPG_Net: Closing duplicate connection "
                        f"{c_addr[0]}:{c_addr[1]}"
                    )
                self._remove_client(c_addr)

    def get_black_and_white_level(self) -> bool | str | tuple[int, int]:
        """Return madVR output level setup.

        Returns:
            tuple: A tuple containing the black level and white level.
        """
        # XXX: madHcNetXX.dll exports madVR_GetBlackAndWhiteLevel,
        # but the equivalent madVR network protocol command is
        # GetBlackWhiteLevel (without the "And")!
        return MadTPGNetSender(self, self._client_socket, "GetBlackWhiteLevel")()

    def get_version(self) -> bool | tuple[str, str, str, str]:
        """Return madVR version.

        Returns:
            bool | tuple[str, str, str, str]: The madVR version as a tuple of
                four strings representing the major, minor, patch, and build
                numbers, or False if the version could not be determined.
        """
        try:
            return (
                self._client_socket
                and self.clients.get(self._client_socket.getpeername(), {}).get(
                    "mvrVersion"
                )
            ) or False
        except OSError as exception:
            if self.debug:
                safe_print("MadTPG_Net:", exception)
            return False

    def _assemble_hello_params(self) -> str:
        """Assemble 'hello' packet parameters.

        Returns:
            str: The assembled parameters for the 'hello' packet.
        """
        info = [
            ("computerName", str(socket.gethostname().upper())),
            ("userName", str(getpass.getuser())),
            ("os", f"{platform.system()} {platform.release()}"),
            ("exeFile", os.path.basename(sys.executable)),
            ("exeVersion", VERSION_STRING),
            ("exeDescr", ""),
            ("exeIcon", ""),
        ]
        params = ""
        for key, value in info:
            params += f"{key}={value}\t"
        return params

    def _hello(self, conn: socket.socket) -> bool:
        """Send 'hello' packet. Return boolean wether send succeeded or not.

        Args:
            conn (socket.socket): The socket connection to send the hello
                packet.

        Returns:
            bool: True if the hello packet was sent successfully, False
                otherwise.
        """
        params = self._assemble_hello_params()
        return self._send(conn, "hello", params, b"")

    def _is_master(self, conn: socket.socket) -> bool:
        """Return wether our end of the connection is the master or not.

        Args:
            conn (socket.socket): The socket connection to check.

        Returns:
            bool: True if our end is the master, False otherwise.
        """
        local = conn.getsockname()
        remote = conn.getpeername()
        return inet_pton(local[0]) > inet_pton(remote[0]) or (
            inet_pton(local[0]) == inet_pton(remote[0])
            and self.clients[remote]["processId"] < os.getpid()
        )

    def _expect(
        self,
        conn: socket.socket,
        commandno: int = -1,
        command: None | str = None,
        params: list | tuple = (),
        component: str = "",
        timeout: float = 3,
    ) -> bool:
        """Wait until expected reply or timeout. Return reply params or False.

        Args:
            conn (socket.socket): The socket connection to wait for replies.
            commandno (int): The command number to wait for, -1 for any.
            command (None | str, optional): The command to wait for, None for
                any.
            params (list | tuple): The parameters to wait for, empty for any.
            component (str): The component to wait for, None for any.
            timeout (float): Timeout in seconds to wait for the reply.

        Returns:
            bool: The reply parameters if found, False if timeout exceeded or
                no reply found.
        """
        if not isinstance(params, (list, tuple)):
            params = (params,)
        try:
            addr = conn.getpeername()
        except OSError as exception:
            safe_print("MadTPG_Net:", exception)
            return False
        start = end = time()
        while end - start < timeout:
            for reply in self._incoming.get(addr, []):
                r_commandno, r_command, r_params, r_component = reply
                if (
                    commandno in (r_commandno, -1)
                    and command in (r_command, None)
                    and not params
                ) or ((r_params in params) and component in (r_component, None)):
                    self._incoming[addr].remove(reply)
                    return r_params
            sleep(0.001)
            end = time()
        if self.debug:
            safe_print("MadTPG_Net: Timeout exceeded while waiting for reply")
        return False

    def _wait_for_client(
        self,
        addr: None | tuple = None,
        timeout: float = 1,
    ) -> bool:
        """Wait for (first) madTPG client connection and handshake.

        Args:
            addr (tuple): Optional address to wait for, if None, wait for any
                client.
            timeout (float): Timeout in seconds to wait for the client.

        Returns:
            bool: True if a madTPG client was found and the StartTestPattern
                command was successfully sent, False otherwise.
        """
        start = end = time()
        while self.listening and end - start < timeout:
            clients = self.clients.copy()
            if clients:
                c_addrs = [addr] if addr else list(clients.keys())
                for c_addr in c_addrs:
                    client = clients.get(c_addr)
                    conn = self._client_sockets.get(c_addr)
                    if not client and not conn:
                        continue
                    component_ = client["component"]
                    if not component_:
                        # not a madvr component so ignore completely
                        continue
                    pid_host = (
                        f"{client.get('processId', '?')}:"
                        f"{client.get('computerName', '')}"
                    )
                    formatted_client = f"[{component_} {pid_host}]"
                    if component_ != b"madTPG":
                        continue
                    if not client.get("confirmed"):
                        safe_print(
                            f"Ignoring unconfirmed madTPG client : {formatted_client}"
                        )
                        continue
                    safe_print(
                        f"Found madTPG, attempting StartTestPattern : {pid_host}"
                    )
                    if self._send(conn, "StartTestPattern"):
                        self._client_socket = conn
                        safe_print(
                            f"Sent StartTestPattern to MadTPG client : {pid_host}"
                        )
                        return True
            sleep(0.001)
            end = time()
        return False

    def _parse(self, blob: bytes = b"") -> tuple:
        """Consume blob, return record + remaining blob.

        Args:
            blob (bytes): The byte string to parse.

        Returns:
            tuple: A tuple containing the parsed record and the remaining blob.
        """
        if len(blob) < 12:
            return None, blob
        self._validate_crc(blob)
        datalen = struct.unpack("<i", blob[4:8])[0]
        if len(blob) < datalen + 12:
            return None, blob
        record = {
            "magic": blob[0:4],
            "len": struct.unpack("<i", blob[4:8])[0],
            "crc": struct.unpack("<i", blob[8:12])[0],
            "processId": struct.unpack("<i", blob[12:16])[0],
            "module": struct.unpack("<q", blob[16:24])[0],
            "commandNo": struct.unpack("<i", blob[24:28])[0],
            "sizeOfComponent": struct.unpack("<i", blob[28:32])[0],
        }
        a = 32
        b = a + record["sizeOfComponent"]
        self._validate_component_size(blob, a, b)
        record["component"] = blob[a:b]
        a = b + 8
        self._validate_instance_size(blob, a, b)
        record["instance"] = struct.unpack("<q", blob[b:a])[0]
        b = a + 4
        self._validate_size_of_command(blob, a, b)
        record["sizeOfCommand"] = struct.unpack("<i", blob[a:b])[0]
        a = b + record["sizeOfCommand"]
        self._validate_command_size(blob, a, b)
        record["command"] = command = blob[b:a].decode()
        b = a + 4
        self._validate_param_sizes(blob, a, b)
        record["sizeOfParams"] = struct.unpack("<i", blob[a:b])[0]
        a = b + record["sizeOfParams"]
        self._validate_packet_params(blob, record, a, b)
        params = blob[b:a]
        if self.debug > 1:
            record["rawParams"] = params
        if command == "hello":
            params = self._add_version_info_to_params(params)
        elif command == "reply":
            params = self._process_command_reply(record, params)
        record["params"] = params
        if self.debug:
            self._log_record_info(record)
        blob = blob[a:]
        return record, blob

    def _validate_crc(self, blob: bytes) -> None:
        """Validate CRC of the madVR packet.

        Args:
            blob (bytes): The byte string to validate.

        Raises:
            ValueError: If the CRC check fails.
        """
        crc = struct.unpack("<I", blob[8:12])[0]
        # Check CRC
        check = crc32(blob[:8]) & 0xFFFFFFFF
        if check != crc:
            raise ValueError(
                "MadTPG_Net: Invalid madVR packet: CRC check "
                f"failed: Expected {crc}, got {check}"
            )

    def _validate_component_size(self, blob: bytes, a: int, b: int) -> None:
        """Validate component size.

        Args:
            blob (bytes): The byte string to validate.
            a (int): The end index of the component in the blob.
            b (int): The start index of the component in the blob.

        Raises:
            ValueError: If the component size is corrupt or does not match the
                expected length.
        """
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected component "
                f"len {b - a}, got {len(blob[a:b])}"
            )

    def _validate_instance_size(self, blob: bytes, a: int, b: int) -> None:
        """Validate instance size.

        Args:
            blob (bytes): The byte string to validate.
            a (int): The end index of the instance in the blob.
            b (int): The start index of the instance in the blob.

        Raises:
            ValueError: If the instance size is corrupt or does not match the
                expected length.
        """
        if a > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected instance "
                f"len {a - b}, got {len(blob[b:a])}"
            )

    def _validate_size_of_command(self, blob: bytes, a: int, b: int) -> None:
        """Validate size of command.

        Args:
            blob (bytes): The byte string to validate.
            a (int): The end index of the command size in the blob.
            b (int): The start index of the command size in the blob.

        Raises:
            ValueError: If the size of the command is corrupt or does not match
                the expected length.
        """
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected sizeOfCommand "
                f"len {b - a}, got {len(blob[a:b])}"
            )

    def _validate_command_size(self, blob: bytes, a: int, b: int) -> None:
        """Validate command size.

        Args:
            blob (bytes): The byte string to validate.
            a (int): The end index of the command in the blob.
            b (int): The start index of the command in the blob.

        Raises:
            ValueError: If the command size is corrupt or does not match the
                expected length.
        """
        if a > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected command "
                f"len {a - b}, got {len(blob[b:a])}"
            )

    def _validate_param_sizes(self, blob: bytes, a: int, b: int) -> None:
        """Validate parameter sizes.

        Args:
            blob (bytes): The byte string to validate.
            a (int): The end index of the parameters in the blob.
            b (int): The start index of the parameters in the blob.

        Raises:
            ValueError: If the parameter sizes are corrupt or do not match the
                expected length.
        """
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected sizeOfParams "
                f"len {b - a}, got {len(blob[a:b])}"
            )

    def _validate_packet_params(
        self, blob: bytes, record: dict, a: int, b: int
    ) -> None:
        """Validate packet parameters.

        Args:
            blob (bytes): The byte string to validate.
            record (dict): The parsed record from the madVR packet.
            a (int): The end index of the parameters in the blob.
            b (int): The start index of the parameters in the blob.

        Raises:
            ValueError: If the parameters are corrupt or do not match the
                expected length.
        """
        if a > record["len"] + 12:
            raise ValueError(
                "Corrupt madVR packet: Expected params "
                f"len {a - b}, got {len(blob[b:a])}"
            )

    def _add_version_info_to_params(self, params: bytes) -> dict:
        """Add madVR version info to 'hello' packet parameters.

        Args:
            params (bytes): The raw parameters from the 'hello' packet.

        Returns:
            dict: A dictionary containing the parsed parameters including
                madVR version information.
        """
        io = StringIO(
            "[Default]\n" + "\n".join(params.decode("UTF-16-LE").strip().split("\t"))
        )
        cfg = CaseSensitiveConfigParser()
        # cfg.readfp(io)
        cfg.read_file(io)
        params = dict(cfg.items("Default"))
        # Convert version strings to tuples with integers
        for param in ("mvr", "exe"):
            param += "Version"
            if param in params:
                values = params[param].split(".")
                for i, value in enumerate(values):
                    with contextlib.suppress(ValueError):
                        values[i] = int(value)
                params[param] = tuple(values)
        return params

    def _process_command_reply(
        self,
        record: dict,
        params: bytes,
    ) -> bool | int | tuple | ctypes.Array:
        """Process command reply parameters.

        Args:
            record (dict): The parsed record from the madVR packet.
            params (bytes): The raw parameters from the madVR packet.

        Returns:
            bool | int | tuple | ctypes.Array: The processed parameters based
                on the command that was replied to, or False if the parameters
                could not be processed.
        """
        commandno = record["commandNo"]
        replied_command = self._commands.get(commandno)
        if replied_command:
            self._commands.pop(commandno)
            # XXX: madHcNetXX.dll exports madVR_GetBlackAndWhiteLevel,
            # but the equivalent madVR network protocol command is
            # GetBlackWhiteLevel (without the "And")!
            if replied_command == "GetBlackWhiteLevel":
                params = struct.unpack("<ii", params) if len(params) == 8 else False
            elif replied_command == "GetDeviceGammaRamp":
                # Convert to ushort_Array_256_Array_3
                ramp = ((ctypes.c_ushort * 256) * 3)()
                if len(params) == 1536:
                    for j in range(3):
                        for i in range(256):
                            ramp[j][i] = round(struct.unpack("<H", params[:2])[0])
                            params = params[2:]
                    params = ramp
                else:
                    params = False
            elif replied_command == "GetPatternConfig":
                params = struct.unpack("<iiii", params) if len(params) == 16 else False
            elif replied_command in ("GetSelected3dlut",):
                params = (
                    struct.unpack("<i", params[0:4])[0] if len(params) == 4 else False
                )
        elif self.debug:
            # Got a reply for a command we never issued?
            safe_print(f"MadTPG_Net: Got reply {commandno} for unknown command")
        return params

    def _log_record_info(self, record: dict) -> None:
        """Log madVR packet record information.

        Args:
            record (dict): The parsed record from the madVR packet.
        """
        with _LOCK:
            safe_print(
                record["processId"],
                record["module"],
                record["commandNo"],
                record["component"],
                record["instance"],
                record["command"],
            )
            for key in record:
                value = record[key]
                if key != "params" and self.debug <= 2:
                    continue
                if isinstance(value, dict):
                    safe_print(f"  {key}:")
                    for subkey in value:
                        subvalue = value[subkey]
                        if self.debug < 2 and subkey != "exeFile":
                            continue
                        safe_print(f"    {subkey.ljust(16)} = {trunc(subvalue, 56)}")
                elif self.debug > 1:
                    safe_print(f"  {key.ljust(16)} = {trunc(value, 58)}")

    def _assemble(
        self,
        conn: socket.socket,
        commandno: int = 1,
        command: str = "",
        params: bytes | str = "",
        component: bytes = b"madTPG",
    ) -> bytes:
        """Assemble packet.

        Args:
            conn (socket.socket): The connection socket to send the command
                through.
            commandno (int): The command number, defaults to 1.
            command (str, optional): The command to send, e.g. "SetOsdText",
                "ShowRGB", etc.
            params (bytes | str): Parameters for the command, can be a string
                or bytes.
            component (bytes): The component name, defaults to b"madTPG".

        Raises:
            OSError: If assembling the command fails.

        Returns:
            bytes: The assembled packet ready to be sent.
        """
        magic = b"mad."
        data = struct.pack("<i", os.getpid())  # processId : 4
        data += struct.pack("<q", id(sys.modules[__name__]))  # module/DLL handle : 8
        data += struct.pack("<i", commandno)  # 4
        data += struct.pack("<i", len(component))  # sizeOfComponent : 4
        data += component
        if component == b"madTPG":
            instance = self.clients.get(conn.getpeername(), {}).get("instance", 0)
        else:
            instance = 0
        data += struct.pack("<q", instance)  # instance : 8
        data += struct.pack("<i", len(command))  # sizeOfCommand : 4
        data += command.encode()
        data += struct.pack("<i", len(params))  # sizeOfParams : 4
        data += params if isinstance(params, bytes) else params.encode("UTF-16-LE")
        datalen = len(data)
        packet = magic + struct.pack("<i", datalen)  # 4 + 4
        packet += struct.pack("<I", crc32(packet) & 0xFFFFFFFF)  # 4
        packet += data
        if self.debug > 1:
            with _LOCK:
                safe_print("MadTPG_Net: Assembled madVR packet:")
                self._parse(packet)
        return packet

    def _send(
        self,
        conn: socket.socket,
        command: str = "",
        params: bytes | str = "",
        component: bytes = b"madTPG",
    ) -> bool:
        """Send madTPG command and return reply.

        Args:
            conn (socket.socket): The connection socket to send the command
                through.
            command (str, optional): The command to send, e.g. "SetOsdText",
                "ShowRGB", etc.
            params (bytes | str): Parameters for the command, can be a string
                or bytes.
            component (bytes): The component name, defaults to b"madTPG".

        Raises:
            OSError: If sending the command fails.

        Returns:
            bool: True if the command was sent successfully, False otherwise.
        """
        if not conn:
            return False
        self._commandno += 1
        commandno = self._commandno
        try:
            packet = self._assemble(conn, commandno, command, params, component)
            bytes_total = len(packet)
            if self.debug:
                addr, port = conn.getpeername()[:2]
                safe_print(
                    f"MadTPG_Net: Sending command {commandno} {command!r} to "
                    f"{addr}:{port}"
                )
            bytes_sent_total = bytes_sent = 0
            while packet:
                try:
                    bytes_sent = conn.send(packet)
                except OSError as exception:
                    if exception.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # Resource temporarily unavailable
                        sleep(0.001)
                        continue
                    raise OSError from exception
                if bytes_sent == 0:
                    raise OSError(errno.ENOLINK, "Link has been severed")
                packet = packet[bytes_sent:]
                bytes_sent_total += bytes_sent
                if self.debug and bytes_sent != bytes_total:
                    safe_print(
                        f"MadTPG_Net: Command {commandno} {command!r} to {addr}:{port},"
                        f" bytes sent: {bytes_sent_total} of {bytes_total} "
                        f"({bytes_sent_total / float(bytes_total):.2%})"
                    )
        except OSError as exception:
            safe_print(
                f"MadTPG_Net: Sending command {commandno} {command!r} failed",
                exception,
            )
            return False
        if command not in (
            "confirm",
            "hello",
            "reply",
            "bye",
        ) and not command.startswith("store:"):
            self._commands[commandno] = command
            # Get reply
            if self.debug:
                safe_print(
                    f"MadTPG_Net: Expecting reply for command {commandno} {command!r}"
                )
            # Should be enough even for slow wireless
            timeout = 300 if command in ("Load3dlut", "LoadHdr3dlut") else 3
            return self._expect(conn, commandno, "reply", timeout=timeout)
        return True

    @property
    def uri(self) -> str:
        """Return the URI of the connected madTPG instance.

        Returns:
            str: The URI in the format "IP:PORT".
        """
        try:
            addr = self._client_socket and self._client_socket.getpeername()[:2]
        except OSError as exception:
            safe_print("MadTPG_Net:", exception)
            addr = None
        return "{}:{}".format(*addr) if addr else ("0.0.0.0", 0)  # noqa: S104


class MadTPGNetSender:
    """madTPG network command sender.

    Args:
        madtpg (MadTPGNet): Instance of MadTPGNet to send commands to.
        conn (socket.socket): Connection socket to send commands through.
        command (str): The command to send, e.g. "SetOsdText", "ShowRGB", etc.
    """

    def __init__(self, madtpg: MadTPGNet, conn: socket.socket, command: str) -> None:
        self.madtpg = madtpg
        self._conn = conn
        if command == "Quit":
            command = "Exit"
        self.command = command

    def __call__(self, *args, **kwargs) -> bool | str | tuple:
        """Send command to madTPG instance and return reply.

        Args:
            *args: Positional arguments for the command.
            **kwargs: Keyword arguments for the command.

        Raises:
            TypeError: If the command requires more arguments than provided.

        Returns:
            bool | str | tuple: The result of the command execution.
        """
        if self.command in ("Load3dlutFile", "LoadHdr3dlutFile"):
            lut = H3DLUT(args[0])
            lutdata = lut.LUTDATA
            self.command = self.command[:-4]  # Strip 'File' from command name
        elif self.command in ("Load3dlutFromArray256", "LoadHdr3dlutFromArray256"):
            lutdata = args[0]
            self.command = self.command[:-12]  # Strip 'File' from command name

        if self.command in ("Load3dlut", "LoadHdr3dlut"):
            params = struct.pack("<i", args[1])  # Save to settings?
            params += struct.pack("<i", args[2])  # 3D LUT slot
            params += lutdata
            if self.command == "LoadHdr3dlut":
                params += struct.pack("<i", args[3])  # HDR to SDR?
        elif self.command == "SetDeviceGammaRamp":
            params = self._process_set_device_gamma_ramp_param(args)
        elif self.command in (
            "SetDisableOsdButton",
            "SetStayOnTopButton",
            "SetUseFullscreenButton",
        ):
            params = "+" if args[0] else "-"
        elif self.command == "SetOsdText":
            params = args[0].encode("UTF-16-LE")
        elif self.command in ("SetPatternConfig", "SetProgressBarPos"):
            params = "|".join(str(v) for v in args)
        elif self.command == "ShowRGB":
            params = self._process_show_rgb_param(args, kwargs)
        else:
            params = str(*args)

        return self.madtpg._send(
            self._conn,
            self.command,
            params if isinstance(params, bytes) else params.encode("UTF-16-LE"),
        )

    def _process_set_device_gamma_ramp_param(self, args: list | tuple) -> bytes:
        """Process SetDeviceGammaRamp parameters.

        Args:
            args (list | tuple): Positional arguments for the
                SetDeviceGammaRamp command.

        Returns:
            bytes: The packed device gamma ramp parameters.
        """
        params = b""
        for j in range(3):
            for i in range(256):
                # Clear device gamma ramp if args[0] is None
                # else convert ushort_Array_256_Array_3 to string
                v = i * 257 if args[0] is None else args[0][j][i]
                params += struct.pack("<H", v)
        return params

    def _process_show_rgb_param(self, args: list | tuple, kwargs: dict) -> str:
        """Process ShowRGB parameters and return formatted string.

        Args:
            args (list | tuple): Positional arguments for the ShowRGB command.
            kwargs (dict): Keyword arguments for the ShowRGB command.

        Raises:
            TypeError: If required RGB values are not provided.

        Returns:
            str: Formatted string of RGB values for the ShowRGB command.
        """
        r = kwargs.get("r")
        g = kwargs.get("g")
        b = kwargs.get("b")
        bgr = kwargs.get("bgr")
        bgg = kwargs.get("bgg")
        bgb = kwargs.get("bgb")
        r, g, b = args[:3] if len(args) >= 3 else (r, g, b)
        bgr = args[3] if len(args) > 3 else bgr
        bgg = args[4] if len(args) > 4 else bgg
        bgb = args[5] if len(args) > 5 else bgb
        rgb = r, g, b
        if None not in (bgr, bgg, bgb):
            self.command += "Ex"
            rgb += (bgr, bgg, bgb)
        if None in (r, g, b):
            raise TypeError(
                "show_rgb() takes at least 4 arguments "
                f"({len([v for v in rgb if v])} given)"
            )
        return "|".join(str(v) for v in rgb)


if __name__ == "__main__":
    from DisplayCAL import config

    config.initcfg()
    lang.init()
    if sys.platform == "win32":
        madtpg = MadTPG()
    else:
        madtpg = MadTPGNet()
    try:
        if madtpg.connect(method3=CM_StartLocalInstance, timeout3=10000):
            res = madtpg.set_osd_text("Hello there")
            print(f"RESULT set_osd_text : {res}")
            # sleep(5)
            res = madtpg.show_rgb(1, 0, 0)
            print(f"RESULT show_rgb : {res}")
            res = madtpg.get_black_and_white_level()
            print(f"RESULT bw level : {res}")
            res = madtpg.get_pattern_config()
            print(f"RESULT pattern_config : {res}")
            res = madtpg.get_version()
            print(f"RESULT version : {res}")
            res = madtpg.get_device_gamma_ramp()
            print(f"RESULT gamma_ramp : {res}")
            res = madtpg.enable_3dlut()
            print(f"RESULT enable_3dlut : {res}")
            res = madtpg.get_selected_3dlut()
            print(f"RESULT selected 3dlut : {res}")
            res = madtpg.disable_3dlut()
            print(f"RESULT disable_3dlut : {res}")
            res = madtpg.is_stay_on_top_button_pressed()
            print(f"RESULT is_stay_on_top_button_pressed : {res}")
            res = madtpg.is_use_fullscreen_button_pressed()
            print(f"RESULT is_use_fullscreen_button_pressed : {res}")
            res = madtpg.is_disable_osd_button_pressed()
            print(f"RESULT is_disable_osd_button_pressed : {res}")
            res = madtpg.set_stay_on_top_button(False)
            print(f"RESULT set_stay_on_top_button : {res}")
            res = madtpg.set_use_fullscreen_button(False)
            print(f"RESULT set_use_fullscreen_button : {res}")
            res = madtpg.set_disable_osd_button(False)
            print(f"RESULT set_disable_osd_button : {res}")
            res = madtpg.show_progress_bar(10)
            print(f"RESULT show_progress_bar : {res}")
            res = madtpg.set_progress_bar_pos(5, 15)
            print(f"RESULT set_progress_bar_pos : {res}")
            res = madtpg.enter_fullscreen()
            print(f"RESULT enter_fullscreen : {res}")
            res = madtpg.is_fullscreen()
            print(f"RESULT is_fullscreen : {res}")
            res = madtpg.leave_fullscreen()
            print(f"RESULT leave_fullscreen : {res}")
            res = madtpg.set_device_gamma_ramp(None)
            print(f"RESULT set_device_gamma_ramp : {res}")
            res = madtpg.disconnect()
            print(f"RESULT disconnect : {res}")
            res = madtpg.quit()
            print(f"RESULT quit : {res}")
    finally:
        madtpg.shutdown()
