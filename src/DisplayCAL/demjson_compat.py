# -*- coding: utf-8 -*-c
"""demjson 1.3 compatibility module"""

from io import StringIO
import json
import sys


DEBUG = False


def decode(txt, strict=False, encoding=None, **kw):
    """Decodes a JSON-encoded string into a Python object.

    If 'strict' is set to True, then only strictly-conforming JSON
    output will be produced.  Note that this means that some types
    of values may not be convertable and will result in a
    JSONEncodeError exception.

    The input string can be either a python string or a python unicode
    string.  If it is already a unicode string, then it is assumed
    that no character set decoding is required.

    However, if you pass in a non-Unicode text string (i.e., a python
    type 'str') then an attempt will be made to auto-detect and decode
    the character encoding.  This will be successful if the input was
    encoded in any of UTF-8, UTF-16 (BE or LE), or UTF-32 (BE or LE),
    and of course plain ASCII works too.

    Note though that if you know the character encoding, then you
    should convert to a unicode string yourself, or pass it the name
    of the 'encoding' to avoid the guessing made by the auto
    detection, as with

        python_object = demjson.decode( input_bytes, encoding='utf8' )

    Optional keywords arguments are ignored.

    """

    if not strict:
        # Remove comments
        io = StringIO()
        escape = False
        prev = None
        expect_comment = False
        in_comment = False
        comment_multiline = False
        in_quote = False
        write = True
        for c in txt:
            if DEBUG:
                sys.stdout.write(c)
            write = True
            if c == "\\":
                if DEBUG:
                    sys.stdout.write("<ESCAPE>")
                escape = True
            elif escape:
                if DEBUG:
                    sys.stdout.write("</ESCAPE>")
                escape = False
            else:
                if not in_quote:
                    if c == "/":
                        if expect_comment:
                            if DEBUG:
                                sys.stdout.write("<COMMENT>")
                            in_comment = True
                            comment_multiline = False
                            expect_comment = False
                        elif in_comment and prev == "*":
                            if DEBUG:
                                sys.stdout.write("</MULTILINECOMMENT>")
                            in_comment = False
                            comment_multiline = False
                            write = False
                        elif not in_comment:
                            if DEBUG:
                                sys.stdout.write("<EXPECT_COMMENT>")
                            expect_comment = True
                    elif c == "*":
                        if expect_comment:
                            if DEBUG:
                                sys.stdout.write("<MULTILINECOMMENT>")
                            in_comment = True
                            comment_multiline = True
                            expect_comment = False
                    elif expect_comment:
                        if DEBUG:
                            sys.stdout.write("</EXPECT_COMMENT>")
                        expect_comment = False
                if c == "\n":
                    if in_comment and not comment_multiline:
                        if DEBUG:
                            sys.stdout.write("</COMMENT>")
                        in_comment = False
                        write = False
                elif c == '"' and not in_comment:
                    if in_quote:
                        if DEBUG:
                            sys.stdout.write("</QUOTE>")
                        in_quote = False
                    else:
                        if DEBUG:
                            sys.stdout.write("<QUOTE>")
                        in_quote = True
            if write and not expect_comment and not in_comment:
                io.write(c)
            prev = c
        txt = io.getvalue()
        if DEBUG:
            sys.stdout.write("\n")
            print("JSON:", txt)

    return json.loads(txt, encoding=encoding, strict=strict)


def encode(obj, strict=False, compactly=True, escape_unicode=False, encoding=None):
    """Encodes a Python object into a JSON-encoded string.

    'strict' is ignored.

    If 'compactly' is set to True, then the resulting string will
    have all extraneous white space removed; if False then the
    string will be "pretty printed" with whitespace and indentation
    added to make it more readable.

    If 'escape_unicode' is set to True, then all non-ASCII characters
    will be represented as a unicode escape sequence; if False then
    the actual real unicode character will be inserted.

    If no encoding is specified (encoding=None) then the output will
    either be a Python string (if entirely ASCII) or a Python unicode
    string type.

    However if an encoding name is given then the returned value will
    be a python string which is the byte sequence encoding the JSON
    value.  As the default/recommended encoding for JSON is UTF-8,
    you should almost always pass in encoding='utf8'.

    """

    if compactly:
        indent = None
        separators = (",", ":")
    else:
        indent = 2
        separators = (",", ": ")

    ensure_ascii = escape_unicode or encoding is not None

    return json.dumps(
        obj,
        ensure_ascii=ensure_ascii,
        indent=indent,
        separators=separators,
        encoding=encoding or "utf-8",
    )
