# -*- coding: utf-8 -*-

# See developers/interfaces/madTPG.h in the madVR package


from configparser import RawConfigParser
from io import StringIO
from binascii import unhexlify
from time import sleep, time
from zlib import crc32
import ctypes
import errno
import getpass
import os
import platform
import socket
import struct
import sys
import threading

if sys.platform == "win32":
    import winreg

if sys.platform == "win32":
    import win32api

from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import colormath
from DisplayCAL import cubeiterator as ci
from DisplayCAL import localization as lang
from DisplayCAL import worker_base
from DisplayCAL.imfile import tiff_get_header
from DisplayCAL.meta import name as appname, version
from DisplayCAL.network import get_network_addr, get_valid_host

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

min_version = (0, 88, 20, 0)

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

_methodnames = (
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

_autonet_methodnames = ("AddConnectionCallback", "Listen", "Announce")

_lock = threading.RLock()


def safe_print(*args):
    with _lock:
        print(*args)


def icc_device_link_to_madvr(
    icc_device_link_filename,
    unity=False,
    colorspace=None,
    hdr=None,
    logfile=sys.stdout,
    convert_video_rgb_to_clut65=False,
    append_linear_cal=True,
):
    """Convert ICC device link profile to madVR 256^3 3D LUT using interpolation

    madvr 3D LUT will be written to:
    <device link filename without extension> + '.3dlut'

    """
    t = time()

    filename, ext = os.path.splitext(icc_device_link_filename)

    h3d_params = dict()

    if filename.endswith(".HDR") or hdr == 2:
        name = os.path.splitext(filename)[0]
        h3d_params.update(
            [("Input_Transfer_Function", "PQ"), ("Output_Transfer_Function", "PQ")]
        )
    elif filename.endswith(".HDR2SDR") or hdr == 1:
        name = os.path.splitext(filename)[0]
        h3d_params["Input_Transfer_Function"] = "PQ"
    else:
        name = filename

    h3d_params.update(
        [
            ("Input_Primaries", []),
            ("Input_Range", (16, 235)),
            ("Output_Range", (16, 235)),
        ]
    )

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
            return False

        rgb_space = colormath.get_rgb_space(key)

        colorspace = colormath.get_rgb_space_primaries_wp_xy(rgb_space)

    colorspace = list(colorspace)

    # Use a D65 white for the 3D LUT Input_Primaries as
    # madVR can only deal correctly with D65
    # Use the same D65 xy values as written by madVR
    # 3D LUT install API (ASTM E308-01)
    colorspace[6:] = [0.31273, 0.32902]

    h3d_params["Input_Primaries"] = colorspace

    # Create madVR 3D LUT
    h3d_stream = StringIO(H3D_HEADER)
    h3dlut = H3DLUT(h3d_stream, check_lut_size=False)
    h3dlut.parametersData = h3d_params
    h3dlut.write(filename + ".3dlut")
    raw = open(filename + ".3dlut", "r+b")
    raw.seek(h3dlut.lutFileOffset)
    # Make sure no longer needed h3DLUT instance can be garbage collected
    del h3dlut

    # Lookup 256^3 values through device link and fill madVR cLUT
    clutres = 256
    clutmax = clutres - 1.0
    if unity:
        logfile.write("Writing unity madVR 3D LUT...\n")
        prevperc = -1
        for a in range(clutres):
            for b in range(clutres):
                for c in range(clutres):
                    # Optimize for speed
                    B, G, R = chr(c), chr(b), chr(a)
                    raw.write(B + B + G + G + R + R)
            perc = round(a / clutmax * 100)
            if perc > prevperc:
                logfile.write("\r%i%%" % perc)
                prevperc = perc
    else:
        link = ICCP.ICCProfile(icc_device_link_filename)
        # Need a worker for abort event handling
        worker = worker_base.WorkerBase()
        # icclu verbose=0 gives a speed increase
        xicclu = worker_base.MP_Xicclu(
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

    if append_linear_cal:
        # Append a MadVR cal1 table to the 3dlut.
        # This can be used to ensure that the Graphics Card VideoLuts
        # are correctly setup to match what the 3dLut is expecting.
        #
        # Note that the calibration curves are full range, never TV encoded output values
        #
        # Format is (little endian):
        #    4 byte magic number 'cal1'
        #    4 byte version = 1
        #    4 byte number per channel entries = 256
        #    4 byte bytes per entry = 2
        #    [3][256] 2 byte entry values. Tables are in RGB order

        raw.write("cal1".encode())
        raw.write(struct.pack("<I", 1))
        raw.write(struct.pack("<I", 256))
        raw.write(struct.pack("<I", 2))
        # Linear (unity) calibration
        for i in range(3):
            for j in range(256):
                raw.write(struct.pack("<H", j * 257))

    raw.close()

    safe_print("")
    if unity:
        msg = "Finished writing unity madVR 3D LUT in"
    else:
        msg = "Finished up-interpolating device link and writing madVR 3D LUT in"
    safe_print(msg, time() - t, "seconds")
    if filename.endswith(".HDR"):
        safe_print(
            "Gamut (rx ry gx gy bx by wx wy):",
            "%.5f %.5f %.5f %.5f %.5f %.5f %.5f %.5f" % tuple(colorspace),
        )
    return True


def inet_pton(ip_string):
    """inet_pton(string) -> packed IP representation

    Convert an IP address in string format to the  packed
    binary format used in low-level network functions.

    """
    if ":" in ip_string:
        # IPv6
        return "".join(
            [unhexlify(block.rjust(4, "0")) for block in ip_string.split(":")]
        )
    else:
        # IPv4
        return "".join([chr(int(block)) for block in ip_string.split(".")])


def trunc(value, length):
    """For string types, return value truncated to length"""
    if isinstance(value, str):
        if len(repr(value)) > length:
            value = value[
                : length - 3 - len(str(length)) - len(repr(value)) + len(value)
            ]
            return "%r[:%i]" % (value, length)
    return repr(value)


class H3DLUT(object):
    """3D LUT file format used by madVR"""

    # https://sourceforge.net/projects/thr3dlut

    def __init__(self, stream_or_filename=None, check_lut_size=True):
        if not stream_or_filename:
            return
        if isinstance(stream_or_filename, str):
            self.fileName = stream_or_filename
            with open(stream_or_filename, "rb") as lut:
                data = lut.read()
        else:
            self.fileName = None
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
        parametersSize = struct.unpack("<l", data[76:80])[0]
        self.lutFileOffset = struct.unpack("<l", data[80:84])[0]
        self.lutCompressionMethod = struct.unpack("<l", data[84:88])[0]
        if self.lutCompressionMethod != 0:
            raise ValueError(
                "Compression method not supported: %i" % self.lutCompressionMethod
            )
        self.lutCompressedSize = struct.unpack("<l", data[88:92])[0]
        self.lutUncompressedSize = struct.unpack("<l", data[92:96])[0]
        self.parametersData = dict()
        for line in (
            data[self.parametersFileOffset : self.parametersFileOffset + parametersSize]
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
                "3DLUT size %i does not match expected size %i"
                % (len(self.LUTDATA), self.lutCompressedSize)
            )
        if len(data) == self.lutFileOffset + self.lutCompressedSize + 1552:
            # Calibration appendended
            self.LUTDATA += data[
                self.lutFileOffset
                + self.lutCompressedSize : self.lutFileOffset
                + self.lutCompressedSize
                + 1552
            ]

    @property
    def data(self):
        parameters_data = []
        for key in self.parametersData:
            values = self.parametersData[key]
            if isinstance(values, str):
                value = values
            else:
                values = list(values)
                for i, value in enumerate(values):
                    if isinstance(value, float):
                        values[i] = "%.5f" % value
                    else:
                        values[i] = "%s" % value
                value = " ".join(values)
            parameters_data.append(("%s %s" % (key, value)).encode())
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
    def source_colorspace(self):
        """Return the 3D LUT source colorspace slot and name as 2-tuple"""
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

    def _get_stream(self, stream_or_filename=None, ext=None):
        if not stream_or_filename:
            stream_or_filename = self.fileName
            if ext:
                stream_or_filename = os.path.splitext(stream_or_filename)[0] + ext
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")
        else:
            stream = stream_or_filename
        return stream

    def write(self, stream_or_filename=None):
        """Write 3D LUT to stream or filename."""
        stream = self._get_stream(stream_or_filename)
        stream.write(self.data)
        if isinstance(stream_or_filename, str):
            if not self.fileName:
                self.fileName = stream_or_filename
            stream.close()

    def write_devicelink(self, stream_or_filename=None):
        """Write 3D LUT to ICC device link."""
        stream = self._get_stream(stream_or_filename, ".icc")

        link = ICCP.ICCProfile()
        link.connectionColorSpace = b"RGB"
        link.profileClass = b"link"
        link.tags.desc = ICCP.TextDescriptionType()
        link.tags.desc.ASCII = os.path.splitext(os.path.basename(stream.name))[0]
        link.tags.cprt = ICCP.TextType(b"text\0\0\0\0No copyright", b"cprt")

        input_grid_steps = (
            2 ** self.inputBitDepth[0]
        )  # Assume equal bitdepth for R, G, B
        if input_grid_steps > 255:
            # madVR 3D LUTs are 256^3, but ICC LUT16Type only supports up to
            # 255^3. As madVR 3D LUTs use video levels encoding, we simply skip
            # the first cLUT entry in each dimension and fix the offset by
            # scaling the input/output shaper curves. That way, only level 1 of
            # 255 will be affected (with black at 16 and white at 235),
            # which isn't used in actual video content.
            clut_grid_steps = 255
        else:
            clut_grid_steps = input_grid_steps
        # Filling a 255^3 list is VERY memory intensive in Python, so we 'fake'
        # the LUT16Type cLUT and only use tag data of offsets/sizes and shaper
        # curves while writing the raw cLUT data directly without going through
        # decoding/re-encoding roundtrip
        A2B0 = ICCP.LUT16Type()
        A2B0.matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        A2B0.input = []
        for i in range(3):
            A2B0.input.append([])
            for j in range(4096):
                A2B0.input[-1].append(
                    min(max(j / 4095.0 * (256 / 255.0) - (256 / 255.0 - 1), 0), 1)
                    * 65535
                )
        input_bytes = len(A2B0.input) * len(A2B0.input[0]) * 2
        A2B0.clut = [[[0] * 3 for i in range(clut_grid_steps)]]  # Fake cLUT
        A2B0.output = []
        for i in range(3):
            A2B0.output.append([])
            for j in range(4096):
                A2B0.output[-1].append(
                    min(max(j / 4095.0 * (256 / 255.0), 0), 1) * 65535
                )
        output_bytes = len(A2B0.output) * len(A2B0.output[0]) * 2
        tagData = A2B0.tagData[: 52 + input_bytes]  # Exclude cLUT and output curves

        # Write actual cLUT
        # XXX Currently only 16 bit RGB data is supported
        samples_per_pixel = 3  # RGB
        bytes_per_sample = self.outputBitDepth / 8
        bytes_per_pixel = samples_per_pixel * bytes_per_sample
        io = StringIO(tagData)
        io.seek(0, 2)  # Position cursor at end
        i = 0
        for R in range(input_grid_steps):
            if not R:
                i += input_grid_steps * input_grid_steps
                continue
            for G in range(input_grid_steps):
                if not G:
                    i += input_grid_steps
                    continue
                for B in range(input_grid_steps):
                    if not B:
                        i += 1
                        continue
                    index = i * samples_per_pixel * bytes_per_sample
                    BGR = self.LUTDATA[index : index + bytes_per_pixel]
                    RGB = BGR[::-1]  # BGR little-endian to RGB big-endian byte order
                    io.write(RGB)
                    i += 1
        io.write(A2B0.tagData[-output_bytes:])  # Append output curves
        io.seek(0)
        link.tags.A2B0 = ICCP.ICCProfileTag(io.read(), "A2B0")

        link.write(stream)

        if isinstance(stream_or_filename, str):
            stream.close()

    def write_tiff(self, stream_or_filename=None):
        """Write 3D LUT to TIFF file."""
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
            BGR = self.LUTDATA[index : index + bytes_per_pixel]
            RGB = BGR[::-1]  # BGR little-endian to RGB big-endian byte order
            stream.write(RGB)

        if isinstance(stream_or_filename, str):
            stream.close()


class MadTPGBase(object):
    """Generic pattern generator compatibility layer"""

    def wait(self):
        self.connect(method2=CM_StartLocalInstance)

    def disconnect_client(self):
        self.disconnect()

    def send(
        self,
        rgb=(0, 0, 0),
        bgrgb=(0, 0, 0),
        bits=None,
        use_video_levels=None,
        x=0,
        y=0,
        w=1,
        h=1,
    ):
        cfg = self.get_pattern_config()
        if cfg:
            self.set_pattern_config(
                int(round((w + h) / 2.0 * 100)),
                int(round(sum(bgrgb) / 3.0 * 100)),
                cfg[2],
                cfg[3],
            )
        self.show_rgb(*rgb + bgrgb)


class MadTPG(MadTPGBase):
    """Minimal madTPG controller class"""

    def __init__(self):
        MadTPGBase.__init__(self)
        self._connection_callbacks = []

        # We only expose stuff we might actually use.
        # Also, as the HDR 3D LUT install API of madVR is relatively recent
        # (September 2017), we do not require it.

        # Find madHcNet32.dll
        clsid = "{E1A8B82A-32CE-4B0D-BE0D-AA68C772E423}"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, r"CLSID\%s\InprocServer32" % clsid
            )
            value, valuetype = winreg.QueryValueEx(key, "")
        except Exception:
            raise RuntimeError(lang.getstr("madvr.not_found"))
        if platform.architecture()[0] == "64bit":
            bits = 64
        else:
            bits = 32
        self.dllpath = os.path.join(os.path.split(value)[0], "madHcNet%i.dll" % bits)
        if not value or not os.path.isfile(self.dllpath):
            raise OSError(lang.getstr("not_found", self.dllpath))
        handle = win32api.LoadLibrary(self.dllpath)
        self.mad = ctypes.WinDLL(self.dllpath, handle=handle)

        try:
            # Set expected return value types
            for methodname in _methodnames + _autonet_methodnames:
                if methodname == "AddConnectionCallback":
                    continue
                if methodname in _autonet_methodnames:
                    prefix = "AutoNet"
                else:
                    prefix = "madVR"
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
        except AttributeError:
            raise RuntimeError(
                lang.getstr(
                    "madhcnet.outdated",
                    tuple(reversed(os.path.split(self.dllpath))) + min_version,
                )
            )

    def __del__(self):
        if hasattr(self, "mad"):
            self.disconnect()

    def __getattr__(self, name):
        # Instead of writing individual method wrappers, we use Python's magic
        # to handle this for us. Note that we're sticking to pythonic method
        # names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

        # Convert from pythonic method name to CamelCase
        methodname = "".join(part.capitalize() for part in name.split("_"))

        # Check if this is a madVR method we support
        if methodname not in _methodnames + _autonet_methodnames:
            raise AttributeError(
                "%r object has no attribute %r" % (self.__class__.__name__, name)
            )

        # Return the method
        if methodname in _autonet_methodnames:
            prefix = "AutoNet"
        else:
            prefix = "madVR"
        return getattr(self.mad, prefix + "_" + methodname)

    def add_connection_callback(self, callback, param, component):
        """Handles callbacks for added/closed connections to playback components

        Leave "component" empty to get notification about all components.

        The callback function has to take eight arguments:
        param, connection, ip, pid, module, component, instance, is_new_instance

        """
        callback = CALLBACK(callback)
        self.mad.AutoNet_AddConnectionCallback(callback, param, component)
        self._connection_callbacks.append(callback)

    def connect(
        self,
        method1=CM_ConnectToLocalInstance,
        timeout1=1000,
        method2=CM_ConnectToLanInstance,
        timeout2=3000,
        method3=CM_ShowListDialog,
        timeout3=0,
        method4=CM_Fail,
        timeout4=0,
        parentwindow=None,
    ):
        """Find, select or launch a madTPG instance and connect to it"""
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

    def get_black_and_white_level(self):
        """Return madVR output level setup"""
        blacklvl, whitelvl = ctypes.c_long(), ctypes.c_long()
        result = self.mad.madVR_GetBlackAndWhiteLevel(
            *[ctypes.byref(v) for v in (blacklvl, whitelvl)]
        )
        return result and (blacklvl.value, whitelvl.value)

    def get_device_gamma_ramp(self):
        """Calls the win32 API 'GetDeviceGammaRamp'"""
        ramp = ((ctypes.c_ushort * 256) * 3)()
        result = self.mad.madVR_GetDeviceGammaRamp(ramp)
        return result and ramp

    def get_pattern_config(self):
        """Return the pattern config as 4-tuple

        Pattern area in percent        1-100
        Background level in percent    0-100
        Background mode                0 = constant gray
                                       1 = APL - gamma light
                                       2 = APL - linear light
        Black border width in pixels   0-100
        """
        area, bglvl, bgmode, border = [ctypes.c_long() for i in range(4)]
        result = self.mad.madVR_GetPatternConfig(
            *[ctypes.byref(v) for v in (area, bglvl, bgmode, border)]
        )
        return result and (area.value, bglvl.value, bgmode.value, border.value)

    def get_selected_3dlut(self):
        thr3dlut = ctypes.c_ulong()
        result = self.mad.madVR_GetSelected3dlut(ctypes.byref(thr3dlut))
        return result and thr3dlut.value

    def get_version(self):
        version = ctypes.c_ulong()
        result = self.mad.madVR_GetVersion(ctypes.byref(version))
        version = tuple(
            struct.unpack(">B", c)[0] for c in struct.pack(">I", version.value)
        )
        return result and version

    def show_rgb(self, r, g, b, bgr=None, bgg=None, bgb=None):
        """Shows a specific RGB color test pattern"""
        if None not in (bgr, bgg, bgb):
            return self.mad.madVR_ShowRGBEx(r, g, b, bgr, bgg, bgb)
        else:
            return self.mad.madVR_ShowRGB(r, g, b)

    @property
    def uri(self):
        return self.dllpath


class MadTPG_Net(MadTPGBase):
    """Implementation of madVR network protocol in pure python"""

    # Wireshark filter to help ananlyze traffic:
    # (tcp.dstport != 1900 and tcp.dstport != 443) or (udp.dstport != 1900 and udp.dstport != 137 and udp.dstport != 138 and udp.dstport != 5355 and udp.dstport != 547 and udp.dstport != 10111)

    def __init__(self):
        MadTPGBase.__init__(self)
        self._cast_sockets = {}
        self._casts = []
        self._client_sockets = dict()
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
        self.clients = dict()
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

    def listen(self):
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
                    name="madVR.ConnectionHandler[%s]" % port,
                    args=(sock, "", port),
                )
                self._threads.append(thread)
                thread.start()
            except socket.error as exception:
                safe_print("MadTPG_Net: TCP Port %i: %s" % (port, exception))
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
                    name="madVR.BroadcastHandler[%s:%s]" % (self.broadcast_ip, port),
                    args=(sock, self.broadcast_ip, port),
                )
                self._threads.append(thread)
                thread.start()
            except socket.error as exception:
                safe_print("MadTPG_Net: UDP Port %i: %s" % (port, exception))
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
                    name="madVR.MulticastHandler[%s:%s]" % (self.multicast_ip, port),
                    args=(sock, self.multicast_ip, port),
                )
                self._threads.append(thread)
                thread.start()
            except socket.error as exception:
                safe_print("MadTPG_Net: UDP Port %i: %s" % (port, exception))

    def bind(self, event_name, handler):
        """Bind a handler to an event"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def unbind(self, event_name, handler=None):
        """Unbind (remove) a handler from an event

        If handler is None, remove all handlers for the event.

        """
        if event_name in self._event_handlers:
            if handler in self._event_handlers[event_name]:
                self._event_handlers[event_name].remove(handler)
                return handler
            else:
                return self._event_handlers.pop(event_name)

    def _dispatch_event(self, event_name, event_data=None):
        """Dispatch events"""
        if self.debug:
            safe_print("MadTPG_Net: Dispatching", event_name)
        for handler in self._event_handlers.get(event_name, []):
            handler(event_data)

    def _reset(self):
        self._client_socket = None

    def _conn_accept_handler(self, sock, host, port):
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
                    "MadTPG_Net: In incoming connection thread for port %i:" % port,
                    exception,
                )
                continue
            except socket.error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                safe_print(
                    "MadTPG_Net: Exception in incoming connection "
                    "thread for %s:%i:" % addr[:2],
                    exception,
                )
                break
            conn.settimeout(0)
            with _lock:
                if self.debug:
                    safe_print(
                        "MadTPG_Net: Incoming connection from %s:%s to %s:%s"
                        % (addr[:2] + conn.getsockname()[:2])
                    )
                if addr in self._client_sockets:
                    if self.debug:
                        safe_print(
                            "MadTPG_Net: Already connected from %s:%s to %s:%s"
                            % (addr[:2] + conn.getsockname()[:2])
                        )
                    self._shutdown(conn, addr)
                else:
                    self._client_sockets[addr] = conn
                    thread = threading.Thread(
                        target=self._receive_handler,
                        name="madVR.Receiver[%s:%s]" % addr[:2],
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

    def _receive_handler(self, addr, conn):
        if self.debug:
            safe_print("MadTPG_Net: Entering receiver thread for %s:%s" % addr[:2])
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
                    "MadTPG_Net: In receiver thread for %s:%i:" % addr[:2], exception
                )
                continue
            except socket.error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.001)
                    continue
                if exception.errno not in (errno.EBADF, errno.ECONNRESET) or self.debug:
                    safe_print(
                        "MadTPG_Net: In receiver thread for %s:%i:" % addr[:2],
                        exception,
                    )
                send_bye = False
                break
            else:
                with _lock:
                    if not incoming:
                        # Connection broken
                        if self.debug:
                            safe_print(
                                "MadTPG_Net: Client %s:%i stopped sending" % addr[:2]
                            )
                        send_bye = False
                        break
                    blob += incoming
                    if self.debug:
                        safe_print("MadTPG_Net: Received from %s:%s:" % addr[:2])
                    while blob and addr in self._client_sockets:
                        try:
                            record, blob = self._parse(blob)
                        except ValueError as exception:
                            safe_print("MadTPG_Net:", exception)
                            # Invalid, discard
                            blob = ""
                        else:
                            if record is None:
                                # Need more data
                                break
                            try:
                                self._process(record, conn)
                            except socket.error as exception:
                                safe_print("MadTPG_Net:", exception)
        with _lock:
            self._remove_client(
                addr, send_bye=addr in self._client_sockets and send_bye
            )
            self._incoming.pop(addr)
        if self.debug:
            safe_print("MadTPG_Net: Exiting receiver thread for %s:%s" % addr[:2])

    def _remove_client(self, addr, send_bye=True):
        """Remove client from list of connected clients"""
        if addr in self._client_sockets:
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
                    safe_print("MadTPG_Net: Removed client %s:%i" % addr[:2])
                self._dispatch_event("on_client_removed", (addr, client))
            if self._client_socket and self._client_socket == conn:
                self._reset()
            self._shutdown(conn, addr)

    def _cast_receive_handler(self, sock, host, port):
        if host == self.broadcast_ip:
            cast = "broadcast"
        elif host == self.multicast_ip:
            cast = "multicast"
        else:
            cast = "unknown"
        if self.debug:
            safe_print(
                "MadTPG_Net: Entering receiver thread for %s port %i" % (cast, port)
            )
        self._cast_sockets[(host, port)] = sock
        while getattr(self, "listening", False):
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout as exception:
                safe_print(
                    "MadTPG_Net: In receiver thread for %s port %i:" % (cast, port),
                    exception,
                )
                continue
            except socket.error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                if exception.errno != errno.ECONNRESET or self.debug:
                    safe_print(
                        "MadTPG_Net: In receiver thread for %s port %i:" % (cast, port),
                        exception,
                    )
                break
            else:
                with _lock:
                    if self.debug:
                        safe_print(
                            "MadTPG_Net: Received %s from %s:%s: %r"
                            % (cast, addr[0], addr[1], data)
                        )
                    if addr not in self._casts:
                        for c_port in self.server_ports:
                            if (addr[0], c_port) in self._client_sockets:
                                if self.debug:
                                    safe_print(
                                        "MadTPG_Net: Already connected to %s:%s"
                                        % (addr[0], c_port)
                                    )
                            elif ("", c_port) in self._server_sockets and addr[
                                0
                            ] in self._ips:
                                if self.debug:
                                    safe_print(
                                        "MadTPG_Net: Don't connect to self %s:%s"
                                        % (addr[0], c_port)
                                    )
                            else:
                                conn = self._get_client_socket(addr[0], c_port)
                                threading.Thread(
                                    target=self._connect,
                                    name="madVR.ConnectToInstance[%s:%s]"
                                    % (addr[0], c_port),
                                    args=(conn, addr[0], c_port),
                                ).start()
                    else:
                        self._casts.remove(addr)
                        if self.debug:
                            safe_print(
                                "MadTPG_Net: Ignoring own %s from %s:%s"
                                % (cast, addr[0], addr[1])
                            )
        self._cast_sockets.pop((host, port))
        self._shutdown(sock, (host, port))
        if self.debug:
            safe_print(
                "MadTPG_Net: Exiting %s receiver thread for port %i" % (cast, port)
            )

    def __del__(self):
        self.shutdown()

    def _shutdown(self, sock, addr):
        try:
            # Will fail if the socket isn't connected, i.e. if there
            # was an error during the call to connect()
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error as exception:
            if exception.errno != errno.ENOTCONN:
                safe_print(
                    "MadTPG_Net: SHUT_RDWR for %s:%i failed:" % addr[:2], exception
                )
        sock.close()

    def shutdown(self):
        self.disconnect()
        self.listening = False
        while self._threads:
            thread = self._threads.pop()
            if thread.is_alive():
                thread.join()

    def __getattr__(self, name):
        # Instead of writing individual method wrappers, we use Python's magic
        # to handle this for us. Note that we're sticking to pythonic method
        # names, so 'disable_3dlut' instead of 'Disable3dlut' etc.

        # Convert from pythonic method name to CamelCase
        methodname = "".join(part.capitalize() for part in name.split("_"))

        if methodname == "ShowRgb":
            methodname = "ShowRGB"

        # Check if this is a madVR method we support
        if methodname not in _methodnames:
            raise AttributeError(
                "%r object has no attribute %r" % (self.__class__.__name__, name)
            )

        # Call the method and return the result
        return MadTPG_Net_Sender(self, self._client_socket, methodname)

    def announce(self):
        """Anounce ourselves"""
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
                    "MadTPG_Net: Sending multicast from %s:%s to port %i"
                    % (addr[0], addr[1], port)
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
                    "MadTPG_Net: Sending broadcast from %s:%s to port %i"
                    % (addr[0], addr[1], port)
                )
            sock.sendall(struct.pack("<i", 0))
            self._shutdown(sock, (self.broadcast_ip, port))

    def connect(
        self,
        method1=CM_ConnectToLanInstance,
        timeout1=4000,
        method2=CM_ShowListDialog,
        timeout2=0,
        method3=CM_Fail,
        timeout3=0,
        method4=CM_Fail,
        timeout4=0,
        parentwindow=None,
    ):
        """Find or select a madTPG instance on the network and connect to it"""
        listened = self.listening
        for i in range(1, 5):
            method = locals()["method%i" % i]
            timeout = locals()["timeout%i" % i] / 1000.0
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

    def connect_to_ip(self, ip, timeout=1000):
        """Connect to madTPG running under a known IP address"""
        ip = socket.gethostbyname(ip)
        for port in self.server_ports:
            conn = self._get_client_socket(ip, port)
            threading.Thread(
                target=self._connect,
                name="madVR.ConnectToInstance[%s:%s]" % (ip, port),
                args=(conn, ip, port, timeout / 1000.0),
            ).start()
        return self._wait_for_client((ip, port), timeout / 1000.0)

    def _get_client_socket(self, host, port, timeout=1):
        """Return a new or existing client socket"""
        if (host, port) in self._client_sockets:
            return self._client_sockets[(host, port)]
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        self._client_sockets[(host, port)] = sock
        return sock

    def _connect(self, sock, host, port, timeout=1):
        """Connect to IP:PORT, return socket"""
        if self.debug:
            safe_print("MadTPG_Net: Connecting to %s:%s..." % (host, port))
        try:
            sock.connect((host, port))
        except socket.error as exception:
            if self.debug:
                safe_print(
                    "MadTPG_Net: Connecting to %s:%s failed:" % (host, port), exception
                )
            with _lock:
                self._remove_client((host, port), False)
        else:
            if self.debug:
                safe_print("MadTPG_Net: Connected to %s:%s" % (host, port))
            sock.settimeout(0)
            thread = threading.Thread(
                target=self._receive_handler,
                name="madVR.Receiver[%s:%s]" % (host, port),
                args=(
                    (host, port),
                    sock,
                ),
            )
            self._threads.append(thread)
            thread.start()

    def disconnect(self, stop=True):
        returnvalue = False
        conn = self._client_socket
        if conn:
            returnvalue = True
            if stop:
                returnvalue = self._send(conn, "StopTestPattern")
        self._reset()
        return returnvalue

    def _process(self, record, conn):
        """Process madVR packet"""
        command = record["command"]
        if command not in ("bye", "confirm", "hello", "reply"):
            # Ignore
            return
        addr = conn.getpeername()
        commandno = record["commandNo"]
        component = record["component"]
        params = record["params"]
        client = dict()
        client["processId"] = record["processId"]
        client["module"] = record["module"]
        client["component"] = component
        client["instance"] = record["instance"]
        if command == "reply":
            if params == "+":
                params = True
            elif params == "-":
                params = False
        elif command == "confirm":
            if addr not in self.clients:
                self.clients[addr] = client
                self._dispatch_event("on_client_added", (addr, self.clients[addr]))
            self.clients[addr]["confirmed"] = True
            self._dispatch_event("on_client_confirmed", (addr, self.clients[addr]))
        elif command == "hello":
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
                                    "MadTPG_Net: Preventing duplicate connection %s:%i"
                                    % addr[:2]
                                )
                            self._remove_client(addr, False)
                            return
                self._dispatch_event("on_client_added", (addr, client))
            else:
                client_copy = self.clients[addr].copy()
                self.clients[addr].update(client)
                if self.clients[addr] != client_copy:
                    self._dispatch_event(
                        "on_client_updated", (addr, self.clients[addr])
                    )
            if (
                not self.clients[addr].get("confirmed")
                and self._is_master(conn)
                and self._send(conn, "confirm", component=b"")
            ):
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
                                "MadTPG_Net: Closing duplicate connection %s:%i"
                                % c_addr[:2]
                            )
                        self._remove_client(c_addr)
        elif command == "bye":
            if self.debug:
                safe_print("MadTPG_Net: Client %s:%i disconnected" % addr[:2])
            self._remove_client(addr)
        self._incoming[addr].append((commandno, command, params, component))

    def get_black_and_white_level(self):
        # XXX: madHcNetXX.dll exports madVR_GetBlackAndWhiteLevel,
        # but the equivalent madVR network protocol command is
        # GetBlackWhiteLevel (without the "And")!
        return MadTPG_Net_Sender(self, self._client_socket, "GetBlackWhiteLevel")()

    def get_version(self):
        """Return madVR version"""
        try:
            return (
                self._client_socket
                and self.clients.get(self._client_socket.getpeername(), {}).get(
                    "mvrVersion"
                )
                or False
            )
        except socket.error as exception:
            if self.debug:
                safe_print("MadTPG_Net:", exception)
            return False

    def _assemble_hello_params(self):
        """Assemble 'hello' packet parameters"""
        info = [
            ("computerName", str(socket.gethostname().upper())),
            ("userName", str(getpass.getuser())),
            ("os", "%s %s" % (platform.system(), platform.release())),
            ("exeFile", os.path.basename(sys.executable)),
            ("exeVersion", version),
            ("exeDescr", ""),
            ("exeIcon", ""),
        ]
        params = ""
        for key, value in info:
            params += "%s=%s\t" % (key, value)
        return params

    def _hello(self, conn):
        """Send 'hello' packet. Return boolean wether send succeeded or not"""
        params = self._assemble_hello_params()
        return self._send(conn, "hello", params, b"")

    def _is_master(self, conn):
        """Return wether our end of the connection is the master or not"""
        local = conn.getsockname()
        remote = conn.getpeername()
        return inet_pton(local[0]) > inet_pton(remote[0]) or (
            inet_pton(local[0]) == inet_pton(remote[0])
            and self.clients[remote]["processId"] < os.getpid()
        )

    def _expect(
        self, conn, commandno=-1, command=None, params=(), component="", timeout=3
    ):
        """Wait until expected reply or timeout. Return reply params or False."""
        if not isinstance(params, (list, tuple)):
            params = (params,)
        try:
            addr = conn.getpeername()
        except socket.error as exception:
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
                    or (r_params in params)
                    and component in (r_component, None)
                ):
                    self._incoming[addr].remove(reply)
                    return r_params
            sleep(0.001)
            end = time()
        if self.debug:
            safe_print("MadTPG_Net: Timeout exceeded while waiting for reply")
        return False

    def _wait_for_client(self, addr=None, timeout=1):
        """Wait for (first) madTPG client connection and handshake"""
        start = end = time()
        while self.listening and end - start < timeout:
            clients = self.clients.copy()
            if clients:
                if addr:
                    c_addrs = [addr]
                else:
                    c_addrs = list(clients.keys())
                for c_addr in c_addrs:
                    client = clients.get(c_addr)
                    conn = self._client_sockets.get(c_addr)
                    if not client and not conn:
                        continue
                    component_ = client["component"]
                    if not component_:
                        # not a madvr component so ignore completely
                        continue
                    pid_host = f'{client.get("processId", "?")}:{client.get("computerName", "")}'
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

    def _parse(self, blob=b""):
        """Consume blob, return record + remaining blob"""
        if len(blob) < 12:
            return None, blob
        crc = struct.unpack("<I", blob[8:12])[0]
        # Check CRC
        check = crc32(blob[:8]) & 0xFFFFFFFF
        if check != crc:
            raise ValueError(
                "MadTPG_Net: Invalid madVR packet: CRC check "
                "failed: Expected %i, got %i" % (crc, check)
            )
        datalen = struct.unpack("<i", blob[4:8])[0]
        if len(blob) < datalen + 12:
            return None, blob
        record = dict(
            [
                ("magic", blob[0:4]),
                ("len", struct.unpack("<i", blob[4:8])[0]),
                ("crc", struct.unpack("<i", blob[8:12])[0]),
                ("processId", struct.unpack("<i", blob[12:16])[0]),
                ("module", struct.unpack("<q", blob[16:24])[0]),
                ("commandNo", struct.unpack("<i", blob[24:28])[0]),
                ("sizeOfComponent", struct.unpack("<i", blob[28:32])[0]),
            ]
        )
        a = 32
        b = a + record["sizeOfComponent"]
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected component "
                "len %i, got %i" % (b - a, len(blob[a:b]))
            )
        record["component"] = blob[a:b]
        a = b + 8
        if a > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected instance "
                "len %i, got %i" % (a - b, len(blob[b:a]))
            )
        record["instance"] = struct.unpack("<q", blob[b:a])[0]
        b = a + 4
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected sizeOfCommand "
                "len %i, got %i" % (b - a, len(blob[a:b]))
            )
        record["sizeOfCommand"] = struct.unpack("<i", blob[a:b])[0]
        a = b + record["sizeOfCommand"]
        if a > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected command "
                "len %i, got %i" % (a - b, len(blob[b:a]))
            )
        record["command"] = command = blob[b:a].decode()
        b = a + 4
        if b > len(blob):
            raise ValueError(
                "Corrupt madVR packet: Expected sizeOfParams "
                "len %i, got %i" % (b - a, len(blob[a:b]))
            )
        record["sizeOfParams"] = struct.unpack("<i", blob[a:b])[0]
        a = b + record["sizeOfParams"]
        if a > record["len"] + 12:
            raise ValueError(
                "Corrupt madVR packet: Expected params "
                "len %i, got %i" % (a - b, len(blob[b:a]))
            )
        params = blob[b:a]
        if self.debug > 1:
            record["rawParams"] = params
        if command == "hello":
            io = StringIO(
                "[Default]\n"
                + "\n".join(params.decode("UTF-16-LE").strip().split("\t"))
            )
            cfg = RawConfigParser()
            cfg.optionxform = str
            # cfg.readfp(io)
            cfg.read_file(io)
            params = dict(cfg.items("Default"))
            # Convert version strings to tuples with integers
            for param in ("mvr", "exe"):
                param += "Version"
                if param in params:
                    values = params[param].split(".")
                    for i, value in enumerate(values):
                        try:
                            values[i] = int(value)
                        except ValueError:
                            pass
                    params[param] = tuple(values)
        elif command == "reply":
            commandno = record["commandNo"]
            repliedcommand = self._commands.get(commandno)
            if repliedcommand:
                self._commands.pop(commandno)
                # XXX: madHcNetXX.dll exports madVR_GetBlackAndWhiteLevel,
                # but the equivalent madVR network protocol command is
                # GetBlackWhiteLevel (without the "And")!
                if repliedcommand == "GetBlackWhiteLevel":
                    if len(params) == 8:
                        params = struct.unpack("<ii", params)
                    else:
                        params = False
                elif repliedcommand == "GetDeviceGammaRamp":
                    # Convert to ushort_Array_256_Array_3
                    ramp = ((ctypes.c_ushort * 256) * 3)()
                    if len(params) == 1536:
                        for j in range(3):
                            for i in range(256):
                                ramp[j][i] = int(
                                    round(struct.unpack("<H", params[:2])[0])
                                )
                                params = params[2:]
                        params = ramp
                    else:
                        params = False
                elif repliedcommand == "GetPatternConfig":
                    if len(params) == 16:
                        params = struct.unpack("<iiii", params)
                    else:
                        params = False
                elif repliedcommand in ("GetSelected3dlut",):
                    if len(params) == 4:
                        params = struct.unpack("<i", params[0:4])[0]
                    else:
                        params = False
            else:
                # Got a reply for a command we never issued?
                if self.debug:
                    safe_print(
                        "MadTPG_Net: Got reply %i for unknown command" % commandno
                    )
        record["params"] = params
        if self.debug:
            with _lock:
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
                    if key == "params" or self.debug > 2:
                        if isinstance(value, dict):
                            safe_print("  %s:" % key)
                            for subkey in value:
                                subvalue = value[subkey]
                                if self.debug < 2 and subkey != "exeFile":
                                    continue
                                safe_print(
                                    "    %s = %s"
                                    % (subkey.ljust(16), trunc(subvalue, 56))
                                )
                        elif self.debug > 1:
                            safe_print("  %s = %s" % (key.ljust(16), trunc(value, 58)))
        blob = blob[a:]
        return record, blob

    def _assemble(self, conn, commandno=1, command="", params="", component=b"madTPG"):
        """Assemble packet"""
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
            with _lock:
                safe_print("MadTPG_Net: Assembled madVR packet:")
                self._parse(packet)
        return packet

    def _send(self, conn, command="", params="", component=b"madTPG"):
        """Send madTPG command and return reply"""
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
                    "MadTPG_Net: Sending command %i %r to %s:%s"
                    % (commandno, command, addr, port)
                )
            bytes_sent_total = bytes_sent = 0
            while packet:
                try:
                    bytes_sent = conn.send(packet)
                except socket.error as exception:
                    if exception.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # Resource temporarily unavailable
                        sleep(0.001)
                        continue
                    else:
                        raise
                if bytes_sent == 0:
                    raise socket.error(errno.ENOLINK, "Link has been severed")
                packet = packet[bytes_sent:]
                bytes_sent_total += bytes_sent
                if self.debug and bytes_sent != bytes_total:
                    safe_print(
                        "MadTPG_Net: Command %i %r to %s:%s, "
                        "bytes sent: %s of %s (%.2f%%)"
                        % (
                            commandno,
                            command,
                            addr,
                            port,
                            bytes_sent_total,
                            bytes_total,
                            bytes_sent_total / float(bytes_total) * 100,
                        )
                    )
        except socket.error as exception:
            safe_print(
                "MadTPG_Net: Sending command %i %r failed" % (commandno, command),
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
                    "MadTPG_Net: Expecting reply for command %i %r"
                    % (commandno, command)
                )
            if command in ("Load3dlut", "LoadHdr3dlut"):
                timeout = 300  # Should be enough even for slow wireless
            else:
                timeout = 3
            return self._expect(conn, commandno, "reply", timeout=timeout)
        return True

    @property
    def uri(self):
        try:
            addr = self._client_socket and self._client_socket.getpeername()[:2]
        except socket.error as exception:
            safe_print("MadTPG_Net:", exception)
            addr = None
        return "%s:%s" % (addr or ("0.0.0.0", 0))


class MadTPG_Net_Sender(object):
    def __init__(self, madtpg, conn, command):
        self.madtpg = madtpg
        self._conn = conn
        if command == "Quit":
            command = "Exit"
        self.command = command

    def __call__(self, *args, **kwargs):
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
            params = b""
            for j in range(3):
                for i in range(256):
                    if args[0] is None:
                        # Clear device gamma ramp
                        v = i * 257
                    else:
                        # Convert ushort_Array_256_Array_3 to string
                        v = args[0][j][i]
                    params += struct.pack("<H", v)
        elif self.command in (
            "SetDisableOsdButton",
            "SetStayOnTopButton",
            "SetUseFullscreenButton",
        ):
            if args[0]:
                params = "+"
            else:
                params = "-"
        elif self.command == "SetOsdText":
            params = args[0].encode("UTF-16-LE")
        elif self.command in ("SetPatternConfig", "SetProgressBarPos"):
            params = "|".join(str(v) for v in args)
        elif self.command == "ShowRGB":
            r, g, b, bgr, bgg, bgb = (None,) * 6
            for name in ("r", "g", "b", "bgr", "bgg", "bgb"):
                locals()[name] = kwargs.get(name)
            if len(args) >= 3:
                r, g, b = args[:3]
            if len(args) > 3:
                bgr = args[3]
            if len(args) > 4:
                bgg = args[4]
            if len(args) > 5:
                bgb = args[5]
            rgb = r, g, b
            if None not in (bgr, bgg, bgb):
                self.command += "Ex"
                rgb += (bgr, bgg, bgb)
            if None in (r, g, b):
                raise TypeError(
                    "show_rgb() takes at least 4 arguments (%i given)"
                    % len([v for v in rgb if v])
                )
            params = "|".join(str(v) for v in rgb)
        else:
            params = str(*args)
        return self.madtpg._send(
            self._conn,
            self.command,
            params if isinstance(params, bytes) else params.encode(),
        )


if __name__ == "__main__":
    from DisplayCAL import config

    config.initcfg()
    lang.init()
    if sys.platform == "win32":
        madtpg = MadTPG()
    else:
        madtpg = MadTPG_Net()
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
