# -*- coding: utf-8 -*-

from time import sleep

# 0install: Make sure imported protobuf is from implementation to ensure
# correct version
import sys

if not getattr(sys, "frozen", False):
    import os
    import re

    for pth in sys.path:
        if os.path.basename(pth).startswith("protobuf-") and re.match(
            r"sha\d+(?:new)?", os.path.basename(os.path.dirname(pth))
        ):
            if "google" in sys.modules:
                del sys.modules["google"]
            try:
                import pkg_resources
            except ImportError:
                import pkgutil
            syspath = sys.path[:]
            sys.path[:] = [pth]
            import google.protobuf

            sys.path[:] = syspath
            break

if sys.version_info[:2] < (3,):
    # zeroconf 0.19.1 is the last version supporting Python 2.x
    # but zeroconf 0.20 lacks a check for Python version
    import zeroconf

    if zeroconf.__version__ > "0.19.1":
        raise ImportError(
            """
Python version > 3.3 required for python-zeroconf %s.
If you need support for Python 2 or Python 3.3 please use version 0.19.1
    """
            % zeroconf.__version__
        )

from pychromecast import get_chromecasts
from pychromecast.controllers import BaseController

from DisplayCAL import localization as lang


class ChromeCastPatternGeneratorController(BaseController):
    def __init__(self):
        super(ChromeCastPatternGeneratorController, self).__init__(
            "urn:x-cast:net.hoech.cast.patterngenerator", "B5C2CBFC"
        )
        self.request_id = 0

    def receive_message(self, message, data):
        return True  # Indicate we handled this message

    def send(
        self,
        rgb=(0, 0, 0),
        bgrgb=(0, 0, 0),
        offset_x=0.5,
        offset_y=0.5,
        h_scale=1,
        v_scale=1,
    ):
        fg = "#%02X%02X%02X" % tuple(round(v * 255) for v in rgb)
        bg = "#%02X%02X%02X" % tuple(round(v * 255) for v in bgrgb)
        self.request_id += 1
        self.send_message(
            {
                "requestId": self.request_id,
                "foreground": fg,
                "offset": [offset_x, offset_y],
                "scale": [h_scale, v_scale],
                "background": bg,
            }
        )


class ChromeCastPatternGenerator(object):
    def __init__(self, name, logfile=None):
        self._controller = ChromeCastPatternGeneratorController()
        self.name = name
        self.listening = False
        self.logfile = logfile

    def disconnect_client(self):
        self.listening = False
        if hasattr(self, "_cc"):
            if self._cc.app_id:
                self._cc.quit_app()
        if hasattr(self, "conn"):
            del self.conn

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
        if w < 1:
            x /= 1.0 - w
        else:
            x = 0
        if h < 1:
            y /= 1.0 - h
        else:
            y = 0
        self._controller.send(rgb, bgrgb, x, y, w * 10, h * 10)

    def wait(self):
        self.listening = True
        if self.logfile:
            self.logfile.write(
                lang.getstr("connecting.to", ("Chromecast", " " + self.name)) + "\n"
            )
        if not hasattr(self, "_cc"):
            # Find our ChromeCast
            try:
                self._cc = next(
                    cc
                    for cc in get_chromecasts()
                    if str(cc.device.friendly_name) == self.name
                )
            except StopIteration:
                self.listening = False
                raise
            self._cc.register_handler(self._controller)
        # Wait for ChromeCast device to be ready
        while self.listening:
            self._cc.wait(0.05)
            if self._cc.status:
                break
        if self.listening:
            # Launch pattern generator app
            self._controller.launch()
            # Wait for it
            while (
                self.listening and self._cc.app_id != self._controller.supporting_app_id
            ):
                sleep(0.05)
            self.conn = True
            print(lang.getstr("connection.established"))


if __name__ == "__main__":
    from DisplayCAL import config

    config.initcfg()
    lang.init()

    pg = ChromeCastPatternGenerator("Smörebröd")

    # Find our ChromeCast and connect to it, then launch the pattern generator
    # app on the ChromeCast device
    pg.wait()

    # Display test color (yellow window on blue background)
    pg.send((1, 1, 0), (0, 0, 1), x=0.375, y=0.375, w=0.25, h=0.25)
