# -*- coding: utf-8 -*-

# http://code.activestate.com/recipes/146306-http-client-to-post-using-multipartform-data/

import http.client
import mimetypes
import uuid


def post_multipart(host, selector, fields, files, charset="UTF-8"):
    """Post fields and files to an http host as multipart/form-data.
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return the server's response page.
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
    """fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be uploaded as files
    Return (content_type, body) ready for httplib.HTTP instance
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


def get_content_type(filename):
    if isinstance(filename, bytes):
        filename = filename.decode("utf-8")
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
