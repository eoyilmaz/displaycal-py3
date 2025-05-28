"""Network utilities: hostname resolution, address retrieval, and custom sockets.

It also includes HTTP redirect handlers for logging or preventing redirections.
"""

from __future__ import annotations

import errno
import os
import socket
import sys
import urllib.error
import urllib.request

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from DisplayCAL import localization as lang
from DisplayCAL.util_str import safe_str


def get_network_addr():
    """Try to get the local machine's network address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Opening a connection on a UDP socket does nothing except give the socket
    # the network address of the (local) machine. We use Google's DNS server
    # as remote address, but could use any valid non-local address (doesn't
    # matter if it is actually reachable)
    try:
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]  # Return network address
    finally:
        s.close()


def get_valid_host(hostname: None | str = None) -> tuple[str, str]:
    """Try to verify the hostname by resolving to an IPv4 address.

    Both hostname with and without .local suffix will be tried if necessary.

    Returns:
        tuple[str, str]: A tuple of hostname, addr
    """
    if hostname is None:
        hostname = socket.gethostname()
    hostnames = [hostname]
    if hostname.endswith(".local"):
        hostnames.insert(0, os.path.splitext(hostname)[0])
    elif "." not in hostname:
        hostnames.insert(0, f"{hostname}.local")

    while hostnames:
        hostname = hostnames.pop()
        try:
            addr = socket.gethostbyname(hostname)
        except OSError as e:
            if not hostnames:
                raise e
        else:
            return hostname, addr
    return None, None


class LoggingHTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Like urllib2.HTTPRedirectHandler, but logs redirections.

    Args:
        req (urllib.request.Request): The request object.
        fp (file-like object): The file-like object containing the response.
        code (int): The HTTP status code.
        msg (str): The HTTP status message.
        headers (dict): The response headers.
    """

    # maximum number of redirections to any single URL
    # this is needed because of the state that cookies introduce
    max_repeats = 4
    # maximum total number of redirections (regardless of URL) before
    # assuming we're in a loop
    max_redirections = 10

    def http_error_302(self, req, fp, code, msg, headers):
        """Handle HTTP 302 redirection error.

        Args:
            req (urllib.request.Request): The request object.
            fp (file-like object): The file-like object containing the
                response.
            code (int): The HTTP status code.
            msg (str): The HTTP status message.
            headers (dict): The response headers.

        Returns:
            None | urllib.request.HTTPRedirectHandler: The HTTP redirect
                handler instance, or None if no redirection is needed.
        """
        # Some servers (incorrectly) return multiple Location headers
        # (so probably same goes for URI).  Use first header.
        if "location" in headers:
            newurl = headers.get("location")
        elif "uri" in headers:
            newurl = headers.get("uri")
        else:
            return None

        # Keep reference to new URL
        LoggingHTTPRedirectHandler.newurl = newurl

        if not hasattr(req, "redirect_dict"):
            # First redirect in this chain. Log original URL
            print(req.get_full_url(), end=" ")
        print("\u2192", newurl)

        return urllib.request.HTTPRedirectHandler.http_error_302(
            self, req, fp, code, msg, headers
        )

    http_error_301 = http_error_303 = http_error_307 = http_error_302

    inf_msg = urllib.request.HTTPRedirectHandler.inf_msg


class NoHTTPRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Like urllib2.HTTPRedirectHandler, but does not allow redirections.

    Args:
        req (urllib.request.Request): The request object.
        fp (file-like object): The file-like object containing the response.
        code (int): The HTTP status code.
        msg (str): The HTTP status message.
        headers (dict): The response headers.
    """

    def http_error_302(self, req, fp, code, msg, headers):
        """Handle HTTP 302 redirection error.

        Args:
            req (urllib.request.Request): The request object.
            fp (file-like object): The file-like object containing the
                response.
            code (int): The HTTP status code.
            msg (str): The HTTP status message.
            headers (dict): The response headers.

        Raises:
            urllib.error.HTTPError: If redirection is not allowed, raises an
                HTTPError with the new URL and the original error message.
        """
        # Some servers (incorrectly) return multiple Location headers
        # (so probably same goes for URI).  Use first header.
        if "location" in headers:
            newurl = headers.get("location")
        elif "uri" in headers:
            newurl = headers.get("uri")
        else:
            return

        raise urllib.error.HTTPError(
            newurl,
            code,
            msg + f" - Redirection to url '{newurl}' is not allowed",
            headers,
            fp,
        )

    http_error_301 = http_error_303 = http_error_307 = http_error_302


class ScriptingClientSocket(socket.socket):
    """A socket class for handling scripting client connections."""

    def __del__(self) -> None:
        """Destructor for the ScriptingClientSocket class."""
        self.disconnect()

    def __enter__(self) -> Self:
        """Enter method for context manager.

        Returns:
            ScriptingClientSocket: The instance of the socket.
        """
        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        """Exit method for context manager.

        Args:
            exc_type (type): The type of the exception raised, if any.
            exc_value (Exception): The exception instance, if any.
            tb (traceback): The traceback object, if any.

        Returns:
            None
        """
        self.disconnect()

    def __init__(self):
        socket.socket.__init__(self)
        self.recv_buffer = b""

    def disconnect(self):
        """Disconnect the socket and clean up resources."""
        try:
            # Will fail if the socket isn't connected, i.e. if there was an
            # error during the call to connect()
            self.shutdown(socket.SHUT_RDWR)
        except OSError as exception:
            if exception.errno != errno.ENOTCONN:
                print(exception)
        self.close()

    def get_single_response(self):
        """Receive a single response from the socket.

        Returns:
            bytes: The single response received from the socket.
        """
        # Buffer received data until EOT (response end marker) and return
        # single response (additional data will still be in the buffer)
        while b"\4" not in self.recv_buffer:
            incoming = self.recv(4096)
            if incoming == b"":
                raise OSError(lang.getstr("connection.broken"))
            self.recv_buffer += incoming
        end = self.recv_buffer.find(b"\4")
        single_response = self.recv_buffer[:end]
        self.recv_buffer = self.recv_buffer[end + 1 :]
        return single_response

    def send_command(self, command):
        """Send a command to the socket.

        Args:
            command (str): The command to send.
        """
        # Automatically append newline (command end marker)
        self.sendall((safe_str(command, "utf-8") + "\n").encode("utf-8"))
