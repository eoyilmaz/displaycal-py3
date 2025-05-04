# -*- coding: utf-8 -*-

"""
Re-implementation of Argyll's webwin in pure python.

"""

import http.server
import time
from urllib.parse import unquote

from DisplayCAL.meta import name as appname, version as appversion


WEBDISP_HTML = (
    r"""<!DOCTYPE html>
<html>
<head>
<title>%s Web Display</title>
<script src="webdisp.js"></script>
<style>
html, body {`
    background: #000;
    margin: 0;
    padding: 0;
    overflow: hidden;
    height: 100%%;
}
#pattern {
    position: absolute;
    left: 45%%;
    top: 45%%;
    width: 10%%;
    height: 10%%;
}
</style>
</head>
<body>
<div id="pattern"></div>
</body>
</html>
"""
    % appname
)

WEBDISP_JS = r"""if (typeof XMLHttpRequest == "undefined") {
    XMLHttpRequest = function () {
        try { return new ActiveXObject("Msxml2.XMLHTTP.6.0"); }
            catch (e) {}
        try { return new ActiveXObject("Msxml2.XMLHTTP.3.0"); }
            catch (e) {}
        try { return new ActiveXObject("Microsoft.XMLHTTP"); }
            catch (e) {}
        throw new Error("This browser does not support XMLHttpRequest.");
    };
}

var cpat = ["#000"];
var oXHR;
var pat;

function XHR_request() {
    oXHR.open("GET", "/ajax/messages?" + encodeURIComponent(cpat.join("|") + "|" + Math.random()), true);
    oXHR.onreadystatechange = XHR_response;
    oXHR.send();
}

function XHR_response() {
    if (oXHR.readyState != 4)
        return;

    if (oXHR.status != 200) {
        return;
    }
    var rt = oXHR.responseText;
    if (rt.charAt(0) == '\r' && rt.charAt(1) == '\n')
        rt = rt.slice(2);
    rt = rt.split("|")
    if (rt[0] && cpat != rt) {
        cpat = rt;
        pat.style.background = rt[1] ? rt[0] : "transparent";  // Older dispwin compat
        document.body.style.background = (rt[1] || rt[0]);  // Older dispwin compat
        if (rt.length == 6) {
            pat.style.left = (rt[2] * 100) + "%";
            pat.style.top = (rt[3] * 100) + "%";
            pat.style.width = (rt[4] * 100) + "%";
            pat.style.height = (rt[5] * 100) + "%";
        }
    }
    setTimeout(XHR_request, 50);
}

window.onload = function() {
    pat = document.getElementById("pattern");

    oXHR = new XMLHttpRequest();
    XHR_request();
};
"""


class WebWinHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP request handler with GET and HEAD commands."""

    server_version = appname + "-WebWinHTTP/" + appversion

    def do_GET(self):
        """Serve a GET request."""
        s = self.send_head()
        if s:
            self.wfile.write(s.encode())

    def do_HEAD(self):
        """Serve a HEAD request."""
        self.send_head()

    def log_message(self, format, *args):
        pass

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a string (which has to be written
        to the outputfile by the caller unless the command was HEAD), or
        None, in which case the caller has nothing further to do.

        """
        if self.path == "/":
            s = WEBDISP_HTML
            ctype = "text/html; charset=UTF-8"
        elif self.path == "/webdisp.js":
            s = WEBDISP_JS
            ctype = "application/javascript"
        elif self.path.startswith("/ajax/messages?"):
            curpat = "|".join(unquote(self.path.split("?").pop()).split("|")[:6])
            while (
                self.server.patterngenerator.listening
                and self.server.patterngenerator.pattern == curpat
            ):
                time.sleep(0.05)
            s = self.server.patterngenerator.pattern
            ctype = "text/plain; charset=UTF-8"
        else:
            self.send_error(404)
            return
        if self.server.patterngenerator.listening:
            try:
                self.send_response(200)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Type", ctype)
                self.end_headers()
                return s
            except BaseException:
                pass
