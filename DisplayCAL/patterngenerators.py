"""Pattern generator clients and servers for HTTP and TCP devices.

It supports sending RGB patterns, managing connections, and handling events for
various pattern generator devices.
"""

import contextlib
import errno
import http.client
import json
import select
import struct
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from socket import (
    AF_INET,
    SHUT_RDWR,
    SO_BROADCAST,
    SO_REUSEADDR,
    SOCK_DGRAM,
    SOCK_STREAM,
    SOL_SOCKET,
    gethostbyname,
    gethostname,
    socket,
    timeout,
)
from socketserver import TCPServer
from time import sleep

from DisplayCAL import localization as lang
from DisplayCAL import webwin
from DisplayCAL.network import get_network_addr
from DisplayCAL.util_http import encode_multipart_formdata

_lock = threading.RLock()


def _eintr_retry(func, *args):
    """Restart a system call interrupted by EINTR"""
    while True:
        try:
            return func(*args)
        except OSError as e:
            if e.args[0] != errno.EINTR:
                raise


def _shutdown(sock, addr):
    try:
        # Will fail if the socket isn't connected, i.e. if there
        # was an error during the call to connect()
        sock.shutdown(SHUT_RDWR)
    except OSError as exception:
        if exception.errno != errno.ENOTCONN:
            print(f"PatternGenerator: SHUT_RDWR for {addr[:2]}:{exception} failed:")
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
        """Wait for the pattern generator server to be available."""
        self.connect()

    def __del__(self) -> None:
        """Clean up the connection and socket."""
        self.disconnect_client()

    def _request(self, method, url, params=None, headers=None, validate=None):
        try:
            self.conn.request(method, url, params, headers or {})
            resp = self.conn.getresponse()
        except (OSError, http.client.HTTPException) as exception:
            # TODO: What is the point of having the except clause here?
            raise exception
        else:
            if resp.status == http.client.OK:
                return self._validate(resp, url, validate)
            raise http.client.HTTPException(f"{resp.status} {resp.reason}")

    def _shutdown(self):
        # Override this method in subclass!
        pass

    def _validate(self, resp, url, validate):
        # Override this method in subclass!
        pass

    def connect(self):
        """Connect to the pattern generator server."""
        self.ip = gethostbyname(self.host)
        self.conn = http.client.HTTPConnection(self.ip, self.port)
        try:
            self.conn.connect()
        except (OSError, http.client.HTTPException):
            del self.conn
            raise

    def disconnect_client(self):
        """Disconnect the current client and clean up resources."""
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
        """Send an RGB color to the pattern generator.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to None.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        # Override this method in subclass!
        # raise NotImplementedError


class GenTCPSockPatternGeneratorServer:
    """Generic pattern generator server using TCP sockets.

    Args:
        port (int): The port number to listen on.
        bits (int): Number of bits per channel.
        use_video_levels (bool): Use video levels for RGB values.
            Defaults to False.
        logfile (file-like object, optional): A file-like object to log
            messages. Defaults to None.
    """

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
        """Wait for a client to connect."""
        self.listening = True
        if self.logfile:
            try:
                host = get_network_addr()
            except OSError:
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

    def __del__(self) -> None:
        """Clean up the connection and socket."""
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
        """Disconnect the current client and clean up resources."""
        self.listening = False
        if hasattr(self, "conn"):
            try:
                self.conn.shutdown(SHUT_RDWR)
            except OSError as exception:
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
        """Send an RGB color to the pattern generator.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        for server, bits in (
            (ResolveLSPatternGeneratorServer, 8),
            (ResolveCMPatternGeneratorServer, 10),
        ):
            server.__dict__["send"](
                self, rgb, bgrgb, bits, use_video_levels, x, y, w, h
            )


class PrismaPatternGeneratorClient(GenHTTPPatternGeneratorClient):
    """Prisma HTTP REST interface.

    Args:
        host (str): The hostname or IP address of the Prisma device.
        port (int, optional): The port number to connect to. Defaults to 80.
        use_video_levels (bool, optional): Use video levels for RGB values.
            Defaults to False.
        logfile (file-like object, optional): A file-like object to log
            messages. Defaults to None.
    """

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
        """Start listening for Prisma devices on the local network."""
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
                    "PrismaPatternGeneratorClient.BroadcastHandler["
                    f"{self.broadcast_ip}:{port}]"
                ),
                args=(sock, self.broadcast_ip, port),
            )
            self._threads.append(thread)
            thread.start()
        except OSError as exception:
            print(f"PrismaPatternGeneratorClient: UDP Port {port:d}: {exception:s}")

    def _cast_receive_handler(self, sock, host, port):
        cast = "broadcast"
        if self.debug:
            print(
                "PrismaPatternGeneratorClient: Entering receiver thread for "
                f"{cast:s} port {port:d}"
            )
        self._cast_sockets[(host, port)] = sock
        while getattr(self, "listening", False):
            try:
                data, addr = sock.recvfrom(4096)
            except timeout as exception:
                print(
                    "PrismaPatternGeneratorClient: In receiver thread for "
                    f"{cast:s} port {port:d}:",
                    exception,
                )
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                if exception.errno != errno.ECONNRESET or self.debug:
                    print(
                        "PrismaPatternGeneratorClient: In receiver thread for "
                        f"{cast:s} port {port:d}:",
                        exception,
                    )
                break
            else:
                with _lock:
                    if self.debug:
                        print(
                            "PrismaPatternGeneratorClient: Received "
                            f"{cast} from {addr[0]}:{addr[1]}: {data}"
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
                f"PrismaPatternGeneratorClient: Exiting {cast:s} "
                f"receiver thread for port {port:d}"
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
                f"{addr[0]}:{addr[1]} to port {port:d}"
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

        Args:
            event_name (str): The name of the event to unbind from.
            handler (callable, optional): The handler to remove. If None,
                remove all handlers for the event. Defaults to None.

        Returns:
            None | callable: The removed handler if it was found, or None if no
                handler was found for the event.
        """
        if event_name not in self._event_handlers:
            return None

        if handler in self._event_handlers[event_name]:
            self._event_handlers[event_name].remove(handler)
            return handler

        return self._event_handlers.pop(event_name)

    def _dispatch_event(self, event_name, event_data=None):
        """Dispatch events.

        Args:
            event_name (str): The name of the event to dispatch.
            event_data (any, optional): Data associated with the event.
                Defaults to None.
        """
        if self.debug:
            print("PrismaPatternGeneratorClient: Dispatching", event_name)
        for handler in self._event_handlers.get(event_name, []):
            handler(event_data)

    def _get_rgb(self, rgb, bgrgb, bits=8, use_video_levels=None):
        """The RGB range should be 0..1.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to 8.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.

        Returns:
            tuple: A tuple containing the RGB and BGRGB values encoded for the
                Prisma HTTP REST interface, and the number of bits per channel.
        """
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
        """Invoke a method on the Prisma device.

        Args:
            api (str): The API endpoint to call.
            method (str, optional): The method to invoke. Defaults to None.
            params (dict, optional): Parameters to pass to the method. Defaults
                to None.
            validate (dict | str, optional): Expected response format or value.

        Returns:
            str | dict: The response from the server, validated against the
                expected format or value.
        """
        url = "/" + api
        if method:
            url += "?m=" + method
            if params:
                url += "&" + urllib.parse.unquote_plus(urllib.parse.urlencode(params))
        if not validate:
            validate = {method: "Ok"}
        return self._request("GET", url, validate=validate)

    def _shutdown(self):
        """Shutdown the Prisma device connection."""
        with contextlib.suppress(Exception):
            self.invoke("window", "off", {"sz": 10})

    def _validate(self, resp, url, validate):
        """Validate the response from the server.

        Args:
            resp (HTTPResponse): The HTTP response object.
            url (str): The URL that was requested.
            validate (dict | str): The expected response format or value.

        Raises:
            http.client.HTTPException: If the response does not match the
                expected format or value.

        Returns:
            str | dict: The validated response data, either as a dictionary or
                raw string.
        """
        raw = resp.read()
        if isinstance(validate, dict):
            data = json.loads(raw)
            components = urllib.parse.urlparse(url)
            # api = components.path[1:]
            query = urllib.parse.parse_qs(components.query)
            if b"m" in query:
                method = query[b"m"][0]
                if data.get(method) == "Error" and "msg" in data:
                    raise http.client.HTTPException(f"{self.host}: {data['msg']}")
            for key in validate:
                value = validate[key]
                if key not in data:
                    raise http.client.HTTPException(
                        lang.getstr(
                            "response.invalid.missing_key", (self.host, key, raw)
                        )
                    )
                if value is not None and data[key] != value:
                    raise http.client.HTTPException(
                        lang.getstr(
                            "response.invalid.value", (self.host, key, value, raw)
                        )
                    )
            data["raw"] = raw
            return data
        if validate and raw != validate:
            raise http.client.HTTPException(
                lang.getstr("response.invalid", (self.host, raw))
            )
        return raw

    def disable_processing(self, size=10):
        """Disable processing on the Prisma device.

        Args:
            size (int): The size of the window to set. Defaults to 10.
        """
        self.enable_processing(False, size)

    def enable_processing(self, enable=True, size=10):
        """Enable or disable processing on the Prisma device.

        Args:
            enable (bool): If True, processing is enabled; if False, it is
                disabled.
            size (int): The size of the window to set. Defaults to 10.
        """
        win = 1 if enable else 2
        self.invoke("Window", f"win{win}", {"sz": size})

    def get_config(self):
        """Get the current configuration of the Prisma device.

        Returns:
            dict: A dictionary containing the current configuration settings.
        """
        return self.invoke("Prisma", "settings", validate={"v": None, "settings": "Ok"})

    def get_installed_3dluts(self):
        """Get a list of installed 3D LUTs.

        Returns:
            dict: A dictionary containing the list of installed 3D LUTs.
        """
        return self.invoke("Cube", "list", validate={"list": "Ok", "v": None})

    def load_preset(self, presetname):
        """Load a preset by name.

        Args:
            presetname (str): The name of the preset to load.
        """
        return self.invoke(
            "Prisma", "loadPreset", {"n": presetname}, validate={"v": None}
        )

    def load_3dlut_file(self, path, filename):
        """Load a 3D LUT file.

        Args:
            path (str): The path to the 3D LUT file.
            filename (str): The name of the 3D LUT file to upload.
        """
        with open(path, "rb") as lut3d:
            data = lut3d.read()
        files = [("cubeFile", filename, data)]
        content_type, params = encode_multipart_formdata([], files)
        headers = {"Content-Type": content_type, "Content-Length": str(len(params))}
        # Upload 3D LUT
        self._request("POST", "/fwupload", params, headers)

    def remove_3dlut(self, filename):
        """Remove a 3D LUT by name.

        Args:
            filename (str): The name of the 3D LUT file to remove.
        """
        self.invoke("Cube", "remove", {"n": filename})

    def set_3dlut(self, filename):
        """Set the 3D LUT by name.

        Args:
            filename (str): The name of the 3D LUT file to set.
        """
        # Select 3D LUT
        self.invoke("Prisma", "setCube", {"n": filename, "f": "null"})

    def set_prismavue(self, value):
        """Set the PrismaVue mode.

        Args:
            value (str): The PrismaVue mode to set. Can be "on", "off", or
                "null".
        """
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
        """Send an RGB color to the pattern generator.

        The RGB range should be 0..1.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to None.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        self.invoke("Window", "color", {"bg": bgrgb, "fg": rgb})
        size = (w + h) / 2.0 * 100
        if size != self._size:
            self._size = size
            self.enable_processing(self._enable_processing, size)


class ResolveLSPatternGeneratorServer(GenTCPSockPatternGeneratorServer):
    """Resolve LS pattern generator server using TCP sockets.

    Args:
        port (int): The port number to listen on. Defaults to 20002.
        bits (int): Number of bits per channel. Defaults to 8.
        use_video_levels (bool): Use video levels for RGB values. Defaults to
            False.
        logfile (file-like object, optional): A file-like object to log
            messages. Defaults to None.
    """

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
        """Send an RGB color to the pattern generator.

        The RGB range should be 0..1.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to None.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        xml = (
            '<?xml version="1.0" encoding="UTF-8" ?><calibration><shapes>'
            "<rectangle>"
            f'<color red="{rgb[0]:d}" green="{rgb[1]:d}" blue="{rgb[2]:d}" />'
            f'<geometry x="{x:.4f}" y="{y:.4f}" cx="{w:.4f}" cy="{h:.4f}" />'
            "</rectangle>"
            "</shapes></calibration>"
        )
        self.conn.sendall(struct.pack(">I", len(xml)) + xml.encode("utf-8"))


class ResolveCMPatternGeneratorServer(GenTCPSockPatternGeneratorServer):
    """Resolve Colorimeter pattern generator server using TCP sockets.

    Args:
        port (int): The port number to listen on. Defaults to 20002.
        bits (int): Number of bits per channel. Defaults to 10.
        use_video_levels (bool): Use video levels for RGB values. Defaults to
            False.
        logfile (file-like object, optional): A file-like object to log
            messages. Defaults to None.
    """

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
        """Send an RGB color to the pattern generator.

        The RGB range should be 0..1.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to None.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        rgb, bgrgb, bits = self._get_rgb(rgb, bgrgb, bits, use_video_levels)
        xml = (
            '<?xml version="1.0" encoding="utf-8"?><calibration>'
            f'<color red="{rgb[0]:d}" green="{rgb[1]:d}" '
            f'blue="{rgb[2]:d}" bits="{bits:d}"/>'
            f'<background red="{bgrgb[0]:d}" green="{bgrgb[1]:d}" '
            f'blue="{bgrgb[2]:d}" bits="{bits:d}"/>'
            f'<geometry x="{x:.4f}" y="{y:.4f}" cx="{w:.4f}" cy="{h:.4f}"/>'
            "</calibration>"
        )
        self.conn.sendall(struct.pack(">I", len(xml)) + xml.encode("utf-8"))


class WebWinHTTPPatternGeneratorServer(TCPServer):
    """WebWin pattern generator server using HTTP REST interface.

    Args:
        port (int): The port number to listen on.
        logfile (file-like object, optional): A file-like object to log
            messages. Defaults to None.
    """

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
        """Disconnect the current client and clean up resources."""
        self.listening = False

    def handle_error(self, request, client_address):
        """Handle errors that occur during request processing.

        Args:
            request (Request): The request object that caused the error.
            client_address (str): The address of the client that made the
                request.
        """
        print(
            "Exception happened during processing of request from "
            f"{client_address}:{sys.exc_info()[1]}:"
        )

    @property
    def listening(self):
        """Check if the server is currently listening for requests.

        Returns:
            bool: True if the server is listening, False otherwise.
        """
        return self._listening.is_set()

    @listening.setter
    def listening(self, value):
        """Set the listening state of the server.

        Args:
            value (bool): If True, the server starts listening for requests.
                If False, it stops listening and cleans up any existing
                connections.
        """
        if value:
            self._listening.set()
            return
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
        """Send an RGB color to the pattern generator. The RGB range should be 0..1.

        Args:
            rgb (tuple): RGB color values in the range 0..1.
            bgrgb (tuple): Background RGB color values in the range 0..1.
            bits (int, optional): Number of bits per channel. Defaults to None.
            use_video_levels (bool, optional): Use video levels for RGB values.
                Defaults to None.
            x (float): X position of the rectangle. Defaults to 0.
            y (float): Y position of the rectangle. Defaults to 0.
            w (float): Width of the rectangle. Defaults to 1.
            h (float): Height of the rectangle. Defaults to 1.
        """
        pattern = [
            "#{:02d}{:02d}{:02d}".format(*tuple(round(v * 255) for v in rgb)),
            "#{:02d}{:02d}{:02d}".format(*tuple(round(v * 255) for v in bgrgb)),
            f"{x:.4f}|{y:.4f}|{w:.4f}|{h:.4f}",
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
        """Stop the serve_forever loop.

        Blocks until the loop has finished. This must be called while
        serve_forever() is running in another thread.
        """
        self._listening.clear()
        while self._thread.is_alive():
            sleep(0.05)

    def wait(self):
        """Wait for a client to connect and process the request."""
        self.listening = True
        if self.logfile:
            try:
                host = get_network_addr()
            except OSError:
                host = gethostname()
            self.logfile.write(
                "{} {}:{}\n".format(lang.getstr("webserver.waiting"), host, self.port)
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
        if not self.listening:
            return
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
