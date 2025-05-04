# -*- coding: utf-8 -*-

import codecs
import locale
import os
import sys

from DisplayCAL.encoding import get_encoding

_codecs = {}
_stdio = {}


def codec_register_alias(alias, name):
    """Register an alias for encoding 'name'"""
    _codecs[alias] = codecs.CodecInfo(
        name=alias,
        encode=codecs.getencoder(name),
        decode=codecs.getdecoder(name),
        incrementalencoder=codecs.getincrementalencoder(name),
        incrementaldecoder=codecs.getincrementaldecoder(name),
        streamwriter=codecs.getwriter(name),
        streamreader=codecs.getreader(name),
    )


def conditional_decode(text, encoding="UTF-8", errors="strict"):
    """Decode text if not unicode"""
    if not isinstance(text, str):
        text = text.decode(encoding, errors)
    return text


def conditional_encode(text, encoding="UTF-8", errors="strict"):
    """Encode text if unicode"""
    if isinstance(text, str):
        text = text.encode(encoding, errors)
    return text


def encodestdio(encodings=None, errors=None):
    """After this function is called, Unicode strings written to
    stdout/stderr are automatically encoded and strings read from stdin
    automatically decoded with the given encodings and error handling.

    encodings and errors can be a dict with mappings for stdin/stdout/stderr,
    e.g. encodings={'stdin': 'UTF-8', 'stdout': 'UTF-8', 'stderr': 'UTF-8'}
    or errors={'stdin': 'strict', 'stdout': 'replace', 'stderr': 'replace'}

    In the case of errors, stdin uses a default 'strict' error handling and
    stdout/stderr both use 'replace'.
    """
    if not encodings:
        encodings = {"stdin": None, "stdout": None, "stderr": None}
    if not errors:
        errors = {"stdin": "strict", "stdout": "replace", "stderr": "replace"}
    for stream_name in set(list(encodings.keys()) + list(errors.keys())):
        stream = getattr(sys, stream_name)
        encoding = encodings.get(stream_name)
        if not encoding:
            encoding = get_encoding(stream)
        error_handling = errors.get(stream_name, "strict")
        if isinstance(stream, EncodedStream):
            stream.encoding = encoding
            stream.errors = error_handling
        else:
            setattr(sys, stream_name, EncodedStream(stream, encoding, error_handling))


def read(stream, size=-1):
    """Read from stream. Uses os.read() if stream is a tty,
    stream.read() otherwise."""
    if stream.isatty():
        data = os.read(stream.fileno(), size)
    else:
        data = stream.read(size)
    return data


def write(stream, data):
    """Write to stream. Uses os.write() if stream is a tty,
    stream.write() otherwise."""
    if stream.isatty():
        os.write(stream.fileno(), data)
    else:
        stream.write(data)


class EncodedStream:
    """Unicode strings written to an EncodedStream are automatically encoded
    and strings read from it automtically decoded with the given encoding
    and error handling.

    Uses os.read() and os.write() for proper handling of unicode codepages
    for stdout/stderr under Windows"""

    def __init__(self, stream, encoding="UTF-8", errors="strict"):
        self.stream = stream
        self.encoding = encoding
        self.errors = errors

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __iter__(self):
        return iter(self.readlines())

    def __setattr__(self, name, value):
        if name == "softspace":
            setattr(self.stream, name, value)
        else:
            object.__setattr__(self, name, value)

    def __next__(self):
        return self.readline()

    def read(self, size=-1):
        return conditional_decode(read(self.stream, size), self.encoding, self.errors)

    def readline(self, size=-1):
        return conditional_decode(
            self.stream.readline(size), self.encoding, self.errors
        )

    def readlines(self, size=-1):
        return [
            conditional_decode(line, self.encoding, self.errors)
            for line in self.stream.readlines(size)
        ]

    def xreadlines(self):
        return self

    def write(self, text):
        write(self.stream, conditional_encode(text, self.encoding, self.errors))

    def writelines(self, lines):
        for line in lines:
            self.write(line)


# Store references to original stdin/stdout/stderr
for _stream_name in ("stdin", "stdout", "stderr"):
    _stream = getattr(sys, _stream_name)
    if isinstance(_stream, EncodedStream):
        _stdio[_stream_name] = _stream.stream
    else:
        _stdio[_stream_name] = _stream

# Register codec aliases for codepages 65000 and 65001
codec_register_alias("65000", "utf_7")
codec_register_alias("65001", "utf_8")
codec_register_alias("cp65000", "utf_7")
codec_register_alias("cp65001", "utf_8")
codecs.register(lambda alias: _codecs.get(alias))

if __name__ == "__main__":
    test = "test \u00e4\u00f6\u00fc\ufffe test"
    try:
        print(test)
    except (LookupError, IOError, UnicodeError) as exception:
        print("could not print %r:" % test, exception)
    print("wrapping stdout/stderr via encodestdio()")
    encodestdio()
    print(test)
    print("exiting normally")
