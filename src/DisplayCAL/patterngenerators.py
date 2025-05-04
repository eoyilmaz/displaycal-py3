# -*- coding: utf-8 -*-

from socketserver import TCPServer
from socket import (
    AF_INET,
    SHUT_RDWR,
    SO_BROADCAST,
    SO_REUSEADDR,
    SOCK_DGRAM,
    SOCK_STREAM,
    SOL_SOCKET,
    error,
    gethostname,
    gethostbyname,
    socket,
    timeout,
)
from time import sleep
import errno
import http.client
import json
import select
import struct
import sys
import threading
import urllib.request
import urllib.error
import urllib.parse

from DisplayCAL import localization as lang
from DisplayCAL.network import get_network_addr
from DisplayCAL.util_http import encode_multipart_formdata
from DisplayCAL import webwin


_lock = threading.RLock()


def _eintr_retry(func, *args):
    """restart a system call interrupted by EINTR"""
    while True:
        try:
            return func(*args)
        except (OSError, select.error) as e:
            if e.args[0] != errno.EINTR:
                raise


def _shutdown(sock, addr):
    try:
        # Will fail if the socket isn't connected, i.e. if there
        # was an error during the call to connect()
        sock.shutdown(SHUT_RDWR)
    except error as exception:
        if exception.errno != errno.ENOTCONN:
            print("PatternGenerator: SHUT_RDWR for %s:%i failed:" % addr[:2], exception)
    sock.close()


class GenHTTPPatternGeneratorClient:
    """Generic pattern generator client using HTTP REST interface"""

    def __init__(self, host, port, bits, use_video_levels=False, logfile=None):
        self.host = host
        self.port = port
        self.bits = bits
        self.use_video_levels = use_video_levels
        self.logfile = logfile

    def wait(self):
        self.connect()

    def __del__(self):
        self.disconnect_client()

    def _request(self, method, url, params=None, headers=None, validate=None):
        try:
            self.conn.request(method, url, params, headers or {})
            resp = self.conn.getresponse()
        except (error, http.client.HTTPException) as exception:
            # TODO: What is the point of having the except clause here?
            raise exception
        else:
            if resp.status == http.client.OK:
                return self._validate(resp, url, validate)
            else:
                raise http.client.HTTPException("%s %s" % (resp.status, resp.reason))

    def _shutdown(self):
        # Override this method in subclass!
        pass

    def _validate(self, resp, url, validate):
        # Override this method in subclass!
        pass

    def connect(self):
        self.ip = gethostbyname(self.host)
        self.conn = http.client.HTTPConnection(self.ip, self.port)
        try:
            self.conn.connect()
        except (error, http.client.HTTPException):
            del self.conn
            raise

    def disconnect_client(self):
        self.listening = False
        if hasattr(self, "conn"):
            self._shutdown()
            self.conn.close()
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
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        # Override this method in subclass!
        # raise NotImplementedError


class GenTCPSockPatternGeneratorServer:
    """Generic pattern generator server using TCP sockets"""

    def __init__(self, port, bits, use_video_levels=False, logfile=None):
        self.port = port
        self.bits = bits
        self.use_video_levels = use_video_levels
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.settimeout(1)
        self.socket.bind(("", port))
        self.socket.listen(1)
        self.listening = False
        self.logfile = logfile

    def wait(self):
        self.listening = True
        if self.logfile:
            try:
                host = get_network_addr()
            except error:
                host = gethostname()
            self.logfile.write(
                "{} {}:{}\n".format(lang.getstr("connection.waiting"), host, self.port)
            )
        while self.listening:
            try:
                self.conn, addr = self.socket.accept()
            except timeout:
                continue
            self.conn.settimeout(1)
            break
        if self.listening:
            print(lang.getstr("connection.established"))

    def __del__(self):
        self.disconnect_client()
        self.socket.close()

    def _get_rgb(self, rgb, bgrgb, bits=None, use_video_levels=None):
        """The RGB range should be 0..1."""
        if not bits:
            bits = self.bits
        if use_video_levels is None:
            use_video_levels = self.use_video_levels
        bitv = 2**bits - 1
        if use_video_levels:
            minv = 16.0 / 255.0
            maxv = 235.0 / 255.0 - minv
            if bits > 8:
                # For video encoding the extra bits of precision are created by
                # bit shifting rather than scaling, so we need to scale the fp
                # value to account for this.
                minv = (minv * 255.0 * (1 << (bits - 8))) / bitv
                maxv = (maxv * 255.0 * (1 << (bits - 8))) / bitv
        else:
            minv = 0.0
            maxv = 1.0
        rgb = [round(minv * bitv + v * bitv * maxv) for v in rgb]
        bgrgb = [round(minv * bitv + v * bitv * maxv) for v in bgrgb]
        return rgb, bgrgb, bits

    def disconnect_client(self):
        self.listening = False
        if hasattr(self, "conn"):
            try:
                self.conn.shutdown(SHUT_RDWR)
            except error as exception:
                if exception.errno != errno.ENOTCONN:
                    print(
                        "Warning - could not shutdown pattern generator connection:",
                        exception,
                    )
            self.conn.close()
            del self.conn

    def send(
        self, rgb=(0, 0, 0), bgrgb=(0, 0, 0), use_video_levels=None, x=0, y=0, w=1, h=1
    ):
        for server, bits in (
            (ResolveLSPatternGeneratorServer, 8),
            (ResolveCMPatternGeneratorServer, 10),
        ):
            server.__dict__["send"](
                self, rgb, bgrgb, bits, use_video_levels, x, y, w, h
            )


class PrismaPatternGeneratorClient(GenHTTPPatternGeneratorClient):
    """Prisma HTTP REST interface"""

    def __init__(self, host, port=80, use_video_levels=False, logfile=None):
        GenHTTPPatternGeneratorClient.__init__(
            self, host, port, 8, use_video_levels=use_video_levels, logfile=logfile
        )
        self.prod_prisma = 2
        self.oem_qinc = 1024
        self.prod_oem = struct.pack("<I", self.prod_prisma) + struct.pack(
            "<I", self.oem_qinc
        )
        # UDP discovery of Prisma devices in local network
        self._cast_sockets = {}
        self._threads = []
        self.broadcast_request_port = 7737
        self.broadcast_response_port = 7747
        self.debug = 0
        self.listening = False
        self._event_handlers = {"on_client_added": []}
        self.broadcast_ip = "255.255.255.255"
        self.prismas = {}
        self._size = 10
        self._enable_processing = True

    def listen(self):
        self.listening = True
        port = self.broadcast_response_port
        if (self.broadcast_ip, port) in self._cast_sockets:
            return
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sock.settimeout(0)
        try:
            sock.bind(("", port))
            thread = threading.Thread(
                target=self._cast_receive_handler,
                name=(
                    "PrismaPatternGeneratorClient.BroadcastHandler[{}:{}]".format(
                        self.broadcast_ip, port
                    )
                ),
                args=(sock, self.broadcast_ip, port),
            )
            self._threads.append(thread)
            thread.start()
        except error as exception:
            print(
                "PrismaPatternGeneratorClient: UDP Port {:d}: {:s}".format(
                    port, exception
                )
            )

    def _cast_receive_handler(self, sock, host, port):
        cast = "broadcast"
        if self.debug:
            print(
                "PrismaPatternGeneratorClient: Entering receiver thread for "
                "{:s} port {:d}".format(cast, port)
            )
        self._cast_sockets[(host, port)] = sock
        while getattr(self, "listening", False):
            try:
                data, addr = sock.recvfrom(4096)
            except timeout as exception:
                print(
                    "PrismaPatternGeneratorClient: In receiver thread for "
                    "{:s} port {:d}:".format(cast, port),
                    exception,
                )
                continue
            except error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                if exception.errno != errno.ECONNRESET or self.debug:
                    print(
                        "PrismaPatternGeneratorClient: In receiver thread for "
                        "{:s} port {:d}:".format(cast, port),
                        exception,
                    )
                break
            else:
                with _lock:
                    if self.debug:
                        print(
                            "PrismaPatternGeneratorClient: Received "
                            "{} from {}:{}: {}".format(cast, addr[0], addr[1], data)
                        )
                    if data.startswith(self.prod_oem):
                        name = data[8:32].rstrip(b"\0")
                        serial = data[32:].rstrip(b"\0")
                        self.prismas[addr[0]] = {"serial": serial, "name": name}
                        self._dispatch_event(
                            "on_client_added", (addr, self.prismas[addr[0]])
                        )
        self._cast_sockets.pop((host, port))
        _shutdown(sock, (host, port))
        if self.debug:
            print(
                "PrismaPatternGeneratorClient: Exiting {:s} receiver thread "
                "for port {:d}".format(cast, port)
            )

    def announce(self):
        """Anounce ourselves."""
        port = self.broadcast_request_port
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sock.settimeout(1)
        sock.connect((self.broadcast_ip, port))
        addr = sock.getsockname()
        if self.debug:
            print(
                "PrismaPatternGeneratorClient: Sending broadcast from "
                "{}:{} to port {:d}".format(addr[0], addr[1], port)
            )
        sock.sendall(self.prod_oem)
        sock.close()

    def bind(self, event_name, handler):
        """Bind a handler to an event."""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    def unbind(self, event_name, handler=None):
        """Unbind (remove) a handler from an event.

        If handler is None, remove all handlers for the event.
        """
        if event_name in self._event_handlers:
            if handler in self._event_handlers[event_name]:
                self._event_handlers[event_name].remove(handler)
                return handler
            else:
                return self._event_handlers.pop(event_name)

    def _dispatch_event(self, event_name, event_data=None):
        """Dispatch events."""
        if self.debug:
            print("PrismaPatternGeneratorClient: Dispatching", event_name)
        for handler in self._event_handlers.get(event_name, []):
            handler(event_data)

    def _get_rgb(self, rgb, bgrgb, bits=8, use_video_levels=None):
        """The RGB range should be 0..1."""
        _get_rgb = GenTCPSockPatternGeneratorServer.__dict__["_get_rgb"]
        rgb, bgrgb, bits = _get_rgb(self, rgb, bgrgb, 8, use_video_levels)
        # Encode RGB values for Prisma HTTP REST interface
        # See prisma-sdk/prisma.cpp, PrismaIo::wincolor
        rgb = [int(round(v)) for v in rgb]
        bgrgb = [int(round(v)) for v in bgrgb]
        rgb = (rgb[0] & 0xFF) << 16 | (rgb[1] & 0xFF) << 8 | (rgb[2] & 0xFF) << 0
        bgrgb = (
            (bgrgb[0] & 0xFF) << 16 | (bgrgb[1] & 0xFF) << 8 | (bgrgb[2] & 0xFF) << 0
        )
        return rgb, bgrgb, bits

    def invoke(self, api, method=None, params=None, validate=None):
        url = "/" + api
        if method:
            url += "?m=" + method
            if params:
                url += "&" + urllib.parse.unquote_plus(urllib.parse.urlencode(params))
        if not validate:
            validate = {method: "Ok"}
        return self._request("GET", url, validate=validate)

    def _shutdown(self):
        try:
            self.invoke("window", "off", {"sz": 10})
        except Exception:
            pass

    def _validate(self, resp, url, validate):
        raw = resp.read()
        if isinstance(validate, dict):
            data = json.loads(raw)
            components = urllib.parse.urlparse(url)
            api = components.path[1:]
            query = urllib.parse.parse_qs(components.query)
            if b"m" in query:
                method = query[b"m"][0]
                if data.get(method) == "Error" and "msg" in data:
                    raise http.client.HTTPException("%s: %s" % (self.host, data["msg"]))
            for key in validate:
                value = validate[key]
                if key not in data:
                    raise http.client.HTTPException(
                        lang.getstr(
                            "response.invalid.missing_key", (self.host, key, raw)
                        )
                    )
                elif value is not None and data[key] != value:
                    raise http.client.HTTPException(
                        lang.getstr(
                            "response.invalid.value", (self.host, key, value, raw)
                        )
                    )
            data["raw"] = raw
            return data
        elif validate:
            if raw != validate:
                raise http.client.HTTPException(
                    lang.getstr("response.invalid", (self.host, raw))
                )
        return raw

    def disable_processing(self, size=10):
        self.enable_processing(False, size)

    def enable_processing(self, enable=True, size=10):
        if enable:
            win = 1
        else:
            win = 2
        self.invoke("Window", "win%i" % win, {"sz": size})

    def get_config(self):
        return self.invoke("Prisma", "settings", validate={"v": None, "settings": "Ok"})

    def get_installed_3dluts(self):
        return self.invoke("Cube", "list", validate={"list": "Ok", "v": None})

    def load_preset(self, presetname):
        return self.invoke(
            "Prisma", "loadPreset", {"n": presetname}, validate={"v": None}
        )

    def load_3dlut_file(self, path, filename):
        with open(path, "rb") as lut3d:
            data = lut3d.read()
        files = [("cubeFile", filename, data)]
        content_type, params = encode_multipart_formdata([], files)
        headers = {"Content-Type": content_type, "Content-Length": str(len(params))}
        # Upload 3D LUT
        self._request("POST", "/fwupload", params, headers)

    def remove_3dlut(self, filename):
        self.invoke("Cube", "remove", {"n": filename})

    def set_3dlut(self, filename):
        # Select 3D LUT
        self.invoke("Prisma", "setCube", {"n": filename, "f": "null"})

    def set_prismavue(self, value):
        self.invoke("Prisma", "setPrismaVue", {"a": value, "t": "null"})

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
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        self.invoke("Window", "color", {"bg": bgrgb, "fg": rgb})
        size = (w + h) / 2.0 * 100
        if size != self._size:
            self._size = size
            self.enable_processing(self._enable_processing, size)


class ResolveLSPatternGeneratorServer(GenTCPSockPatternGeneratorServer):
    def __init__(self, port=20002, bits=8, use_video_levels=False, logfile=None):
        GenTCPSockPatternGeneratorServer.__init__(
            self, port, bits, use_video_levels, logfile
        )

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
        """Send an RGB color to the pattern generator. The RGB range should be 0..1"""
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        xml = (
            '<?xml version="1.0" encoding="UTF-8" ?><calibration><shapes>'
            '<rectangle><color red="{:d}" green="{:d}" blue="{:d}" />'
            '<geometry x="{:.4f}" y="{:.4f}" cx="{:.4f}" cy="{:.4f}" />'
            "</rectangle>"
            "</shapes></calibration>".format(*tuple(rgb + [x, y, w, h]))
        )
        self.conn.sendall(struct.pack(">I", len(xml)) + xml.encode("utf-8"))


class ResolveCMPatternGeneratorServer(GenTCPSockPatternGeneratorServer):
    def __init__(self, port=20002, bits=10, use_video_levels=False, logfile=None):
        GenTCPSockPatternGeneratorServer.__init__(
            self, port, bits, use_video_levels, logfile
        )

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
        """Send an RGB color to the pattern generator. The RGB range should be 0..1"""
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        xml = (
            '<?xml version="1.0" encoding="utf-8"?><calibration>'
            '<color red="{:d}" green="{:d}" blue="{:d}" bits="{:d}"/>'
            '<background red="{:d}" green="{:d}" blue="{:d}" bits="{:d}"/>'
            '<geometry x="{:.4f}" y="{:.4f}" cx="{:.4f}" cy="{:.4f}"/>'
            "</calibration>".format(*tuple(rgb + [bits] + bgrgb + [bits, x, y, w, h]))
        )
        self.conn.sendall(struct.pack(">I", len(xml)) + xml.encode("utf-8"))


class WebWinHTTPPatternGeneratorServer(TCPServer, object):
    def __init__(self, port, logfile=None):
        self.port = port
        Handler = webwin.WebWinHTTPRequestHandler
        TCPServer.__init__(self, ("", port), Handler)
        self.timeout = 1
        self.patterngenerator = self
        self._listening = threading.Event()
        self.logfile = logfile
        self.pattern = "#808080|#808080|0|0|1|1"

    def disconnect_client(self):
        self.listening = False

    def handle_error(self, request, client_address):
        print(
            "Exception happened during processing of request from {}:{}:".format(
                client_address, sys.exc_info()[1]
            )
        )

    @property
    def listening(self):
        return self._listening.is_set()

    @listening.setter
    def listening(self, value):
        if value:
            self._listening.set()
        else:
            self._listening.clear()
            if hasattr(self, "conn"):
                self.shutdown_request(self.conn)
                del self.conn
            if hasattr(self, "_thread") and self._thread.is_alive():
                self.shutdown()

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
        pattern = [
            "#{:02d}{:02d}{:02d}".format(*tuple(round(v * 255) for v in rgb)),
            "#{:02d}{:02d}{:02d}".format(*tuple(round(v * 255) for v in bgrgb)),
            "{:.4f}|{:.4f}|{:.4f}|{:.4f}".format(x, y, w, h),
        ]
        self.pattern = "|".join(pattern)

    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        try:
            while self._listening.is_set():
                # XXX: Consider using another file descriptor or
                # connecting to the socket to wake this up instead of
                # polling. Polling reduces our responsiveness to a
                # shutdown request and wastes cpu at all other times.
                r, w, e = _eintr_retry(select.select, [self], [], [], poll_interval)
                if self in r:
                    self._handle_request_noblock()
        except Exception as exception:
            print(
                "Exception in WebWinHTTPPatternGeneratorServer.serve_forever:",
                exception,
            )
            self._listening.clear()

    def shutdown(self):
        """Stops the serve_forever loop.

        Blocks until the loop has finished. This must be called while
        serve_forever() is running in another thread.
        """
        self._listening.clear()
        while self._thread.is_alive():
            sleep(0.05)

    def wait(self):
        self.listening = True
        if self.logfile:
            try:
                host = get_network_addr()
            except error:
                host = gethostname()
            self.logfile.write(
                ("{} {}:{}\n".format(lang.getstr("webserver.waiting"), host, self.port))
            )
        self.socket.settimeout(1)
        while self.listening:
            try:
                self.conn, addr = self.get_request()
            except timeout:
                continue
            self.conn.settimeout(1)
            break
        self.socket.settimeout(None)
        if self.listening:
            try:
                self.process_request(self.conn, addr)
            except Exception:
                self.handle_error(self.conn, addr)
                self.disconnect_client()
            else:
                self._thread = threading.Thread(
                    target=self.serve_forever,
                    name="WebWinHTTPPatternGeneratorServerThread",
                )
                self._thread.start()
                print(lang.getstr("connection.established"))


if __name__ == "__main__":
    patterngenerator = GenTCPSockPatternGeneratorServer()
