"""This module provides utility functions for making HTTP requests with
multipart/form-data encoding. It includes functions to post fields and
files to an HTTP host and to encode data for multipart form submissions.
"""
# http://code.activestate.com/recipes/146306-http-client-to-post-using-multipartform-data/

from __future__ import annotations

import http.client
import mimetypes
import uuid


def post_multipart(host, selector, fields, files, charset="UTF-8"):
    """Post fields and files to an http host as multipart/form-data.

    Args:
        host: The host to post to.
        selector: The URL path to post to.
        fields: A sequence of (name, value) elements for regular form fields.
        files: A sequence of (name, filename, value) elements for data to be
            uploaded as files.
        charset: The character set to use for encoding the fields and files.

    Returns:
        : the server's response page.
    """
    content_type, body = encode_multipart_formdata(fields, files, charset)
    h = http.client.HTTPConnection(host)
    h.putrequest("POST", selector)
    h.putheader("Content-Type", content_type)
    h.putheader("Content-Length", str(len(body)))
    h.endheaders()
    h.send(body)
    resp = h.getresponse()
    return resp.read()


def encode_multipart_formdata(fields, files, charset="UTF-8"):
    """Encode fields and files for multipart/form-data.

    Args:
        fields (tuple | list): A sequence of (name, value) elements for regular
            form fields.
        files (tuple | list): A sequence of (name, filename, value) elements
            for data to be uploaded as files.
        charset (str): The character set to use for encoding the fields and
            files.

    Returns:
        tuple[content_type, body]: Ready for httplib.HTTP instance.
    """
    BOUNDARY = b"----=_NextPart_" + uuid.uuid1().bytes
    CRLF = b"\r\n"
    L = []
    for key, value in fields:
        if isinstance(key, str):
            key = key.encode(charset)
        if isinstance(value, str):
            value = value.encode(charset)

        L.append(b"--" + BOUNDARY)
        L.append(b'Content-Disposition: form-data; name="' + key + b'"')
        L.append(b"Content-Type: text/plain; charset=" + charset.encode(charset))
        L.append(b"")
        L.append(value)

    for key, filename, value in files:
        if isinstance(key, str):
            key = key.encode(charset)
        if isinstance(filename, str):
            filename = filename.encode(charset)
        if isinstance(value, str):
            value = value.encode(charset)

        L.append(b"--" + BOUNDARY)
        L.append(
            b'Content-Disposition: form-data; name="'
            + key
            + b'"; filename="'
            + filename
            + b'"'
        )
        L.append(b"Content-Type: " + get_content_type(filename).encode(charset))
        L.append(b"")
        L.append(value)

    L.append(b"--" + BOUNDARY + b"--")
    L.append(b"")
    body = CRLF.join(L)
    content_type = b"multipart/form-data; boundary=" + BOUNDARY

    return content_type, body


def get_content_type(filename: str | bytes) -> str:
    """Get the content type of a file based on its filename.

    Args:
        filename (str | bytes): The filename to get the content type for.

    Returns:
        str: The content type of the file.
    """
    if isinstance(filename, bytes):
        filename = filename.decode("utf-8")
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
