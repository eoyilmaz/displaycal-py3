# -*- coding: utf-8 -*-


import re

from DisplayCAL.util_str import strtr

instruments = {
    # instrument names from Argyll source spectro/insttypes.c
    #
    # vid: USB Vendor ID
    #
    # pid: USB Product ID
    #
    # hid: Is the device a USB HID (Human Interface Device) class device?
    #
    # spectral: Does the instrument support spectral readings?
    #
    # adaptive_mode: Does the instrument support adaptive emissive readings?
    #
    # highres_mode: Does the instrument support high-res spectral readings?
    #
    # projector_mode: Does the instrument support a special projector mode?
    #
    # sensor_cal: Does the instrument need to calibrate its sensor by putting
    #             it on a reference tile or black surface?
    #             A value of False for sensor_cal means the instrument can be
    #             left on the display
    #             A value of True for sensor_cal means the instrument must be
    #             removed from the display for sensor calibration if it cannot
    #             be skipped
    #
    # skip_sensor_cal: Can the sensor calibration be skipped?
    #
    # integration_time: Approx. integration time (seconds) for black and white,
    #                   based on measurements on wide-gamut IPS display with
    #                   0.23 cd/m2 black and 130 cd/m2 white level, rounded to
    #                   multiple of .1 seconds.
    #                   Instruments which I don't own have been estimated.
    #
    # refresh: Can the instrument do refresh rate measurements?
    #
    # spectral_cal: Does the instrument support spectral sample (CCSS)
    #               calibration?
    #
    # A missing key, or a value of None, means unknown/not tested
    #
    # Instruments can have an id (short string) that is different than the
    # long instrument name. In case no id is given, the instrument name is
    # the same as the id.
    # TODO: Update instrument names from Argyll 2.3.0
    "DTP92": {
        "usb_ids": [{"vid": 0x0765, "pid": 0xD092, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "refresh": True,
    },
    "DTP94": {
        "usb_ids": [{"vid": 0x0765, "pid": 0xD094, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": False,
        "skip_sensor_cal": False,  # DTP94 instrument access fails
        # when using -N option to skip automatic sensor calibration
        # (dispread -D9 output: "Setting no-sensor_calibrate failed
        # with 'Unsupported function'")
        "integration_time": [4.0, 1.1],  # Estimated
        "refresh": True,
    },
    "Spectrolino": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
    },
    "SpectroScan": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
    },
    "SpectroScanT": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
    },
    "Spectrocam": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": None,
    },
    "i1 Display": {  # Argyll 1.3.5 and earlier
        "usb_ids": [{"vid": 0x0670, "pid": 0x0001, "hid": False}],
        "id": "i1D1",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": False,
        "skip_sensor_cal": False,
        "integration_time": [4.0, 1.0],  # Using i1D2 values
        "refresh": True,
    },
    "i1 Display 1": {  # Argyll 1.3.6 and newer
        "usb_ids": [{"vid": 0x0670, "pid": 0x0001, "hid": False}],
        "id": "i1D1",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": False,
        "integration_time": [4.0, 1.0],  # Using i1D2 values
        "refresh": True,
    },
    "i1 Display 2": {  # Argyll 1.3.6 and newer
        "usb_ids": [{"vid": 0x0971, "pid": 0x2003, "hid": False}],
        "id": "i1D2",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": False,
        "skip_sensor_cal": False,  # i1 Display 2 instrument access fails
        # when using -N option to skip automatic sensor calibration
        # (dispread -D9 output: "Setting no-sensor_calibrate failed
        # with 'Unsupported function'")
        "integration_time": [4.0, 1.0],  # Measured
        "refresh": True,
    },
    "i1 DisplayPro, ColorMunki Display": {
        "usb_ids": [{"vid": 0x0765, "pid": 0x5020, "hid": True}],
        "id": "i1D3",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": False,
        "skip_sensor_cal": False,
        "measurement_mode_map": {"c": "r", "l": "n"},
        "integration_time": [2.6, 0.2],  # Measured
        "refresh": True,
        "spectral_cal": True,
    },
    "i1 Monitor": {  # like i1Pro
        "usb_ids": [{"vid": 0x0971, "pid": 0x2001, "hid": False}],
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Using i1 Pro values
        "refresh": True,
    },
    "i1 Pro": {
        "usb_ids": [{"vid": 0x0971, "pid": 0x2000, "hid": False}],
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Measured (i1 Pro Rev. A)
        "refresh": True,
    },
    "i1 Pro 2": {
        "usb_ids": [{"vid": 0x0971, "pid": 0x2000, "hid": False}],
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Using i1 Pro values
        "refresh": True,
    },
    "i1 Pro 3": {
        "usb_ids": [{"vid": 0x0765, "pid": 0x6009, "hid": False}],
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Still just using i1 Pro values
        "refresh": True,
    },
    "ColorHug": {
        "usb_ids": [
            {"vid": 0x04D8, "pid": 0xF8DA, "hid": True},
            {"vid": 0x273F, "pid": 0x1001, "hid": True},
        ],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [1.8, 0.8],  # Measured (ColorHug #660)
        "refresh": True,
    },
    "ColorHug2": {
        "usb_ids": [{"vid": 0x273F, "pid": 0x1004, "hid": True}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [2.0, 0.6],  # Measured (ColorHug2 prototype #2)
        "refresh": True,
    },
    "ColorMunki": {
        "usb_ids": [
            {"vid": 0x0971, "pid": 0x2007, "hid": False},
            {"vid": 0x0765, "pid": 0x6008, "hid": False},  # ColorMunki i1Studio
        ],
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": True,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Using i1 Pro values
        "refresh": True,
    },
    "Colorimtre HCFR": {
        "usb_ids": [
            {"vid": 0x04DB, "pid": 0x005B, "hid": False},  # V3.1
            {"vid": 0x04D8, "pid": 0xFE17, "hid": False},  # V4.0
        ],
        "id": "HCFR",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
    },
    "ColorMunki Smile": {  # Argyll 1.5.x and newer
        "usb_ids": [{"vid": 0x0765, "pid": 0x6003, "hid": False}],
        "id": "Smile",
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": False,
        "skip_sensor_cal": False,
        "integration_time": [4.0, 1.0],  # Using i1D2 values
    },
    "EX1": {
        "usb_ids": [{"vid": 0x2457, "pid": 0x4000, "hid": False}],
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,
        "integration_time": [9.2, 3.9],  # Using i1 Pro values
    },
    "K-10": {
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [1.1, 0.1],  # Using i1D3 values halved
        "refresh": True,
    },
    "Spyder1": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0100, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [10.5, 2.3],  # Using Spyder3 values
    },
    "Spyder2": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0200, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [10.5, 2.3],  # Using Spyder3 values
        "refresh": True,
    },
    "Spyder3": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0300, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "measurement_mode_map": {"c": "r", "l": "n"},
        "integration_time": [10.5, 2.3],  # Estimated
        "refresh": True,
    },
    "Spyder4": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0400, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "measurement_mode_map": {"c": "r", "l": "n"},
        "integration_time": [10.5, 2.3],  # Using Spyder3 values
        "refresh": True,
        "spectral_cal": True,
    },
    "Spyder5": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0500, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "measurement_mode_map": {"c": "r", "l": "n"},
        "integration_time": [10.5, 2.3],  # Using Spyder3 values
        "refresh": True,
        "spectral_cal": True,
    },
    "SpyderX": {
        "usb_ids": [{"vid": 0x085C, "pid": 0x0A00, "hid": False}],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": True,
        "skip_sensor_cal": True,  # Not yet officially, but likely supported in future
        "integration_time": [1.6, 1.6],
        "refresh": False,
    },
    "Huey": {
        "usb_ids": [
            {"vid": 0x0971, "pid": 0x2005, "hid": True},
            {"vid": 0x0765, "pid": 0x5001, "hid": True},  # HueyL
            {"vid": 0x0765, "pid": 0x5010, "hid": True},  # HueyL
        ],
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [4.0, 1.0],  # Using i1D2 values
    },
    "specbos": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "measurement_mode_map": {"c": "r", "l": "n"},
        "integration_time": [3.3, 0.8],  # Estimated, VERY rough
        "refresh": True,
    },
    "specbos 1201": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [10.3, 2.8],  # Estimated, VERY rough
        "refresh": True,
    },
    "spectraval": {
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": False,
        "projector_mode": False,
        "sensor_cal": None,
        "skip_sensor_cal": None,
        "integration_time": [3.3, 0.8],  # Estimated, VERY rough
        "refresh": True,
    },
    "Dummy Meter / Hires & Projector": {
        # dummy instrument, just for testing
        "spectral": False,
        "adaptive_mode": False,
        "highres_mode": True,
        "projector_mode": True,
        "sensor_cal": False,
        "skip_sensor_cal": False,
    },
    "Dummy Spectro / Hires & Projector": {
        # dummy instrument, just for testing
        "spectral": True,
        "adaptive_mode": False,
        "highres_mode": True,
        "projector_mode": True,
        "sensor_cal": True,
        "skip_sensor_cal": True,
    },
    "Dummy Meter / Adaptive, Hires & Projector": {
        # dummy instrument, just for testing
        "spectral": False,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": True,
        "sensor_cal": False,
        "skip_sensor_cal": False,
    },
    "Dummy Spectro / Adaptive, Hires & Projector": {
        # dummy instrument, just for testing
        "spectral": True,
        "adaptive_mode": True,
        "highres_mode": True,
        "projector_mode": True,
        "sensor_cal": True,
        "skip_sensor_cal": True,
    },
}

vendors = [
    "ColorVision",
    "Datacolor",
    "GretagMacbeth",
    "Hughski",
    "Image Engineering",
    "JETI",
    "Klein",
    "X-Rite",
    "Xrite",
]


def get_canonical_instrument_name(instrument_name, replacements=None, inverse=False):
    """

    :param (bytes, str) instrument_name:
    :param replacements:
    :param inverse:
    :return:
    """
    replacements = replacements or {}
    if inverse:
        replacements = dict(zip(iter(replacements.values()), iter(replacements.keys())))
    return strtr(remove_vendor_names(instrument_name), replacements)


def remove_vendor_names(txt):
    for vendor in vendors:
        if isinstance(txt, bytes):
            txt = re.sub(
                re.compile(re.escape(bytes(vendor, "utf-8")) + rb"\s*", re.I), b"", txt
            )
        elif isinstance(txt, str):
            txt = re.sub(re.compile(re.escape(vendor) + r"\s*", re.I), "", txt)
            txt = txt.strip()
    return txt
