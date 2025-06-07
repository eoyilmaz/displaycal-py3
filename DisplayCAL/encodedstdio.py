"""Utilities for handling encoded input/output streams.

Includes codec alias registration and automatic encoding/decoding for standard
streams.
"""

import codecs
import os
import sys
from collections.abc import Iterator
from typing import Any

from DisplayCAL.encoding import get_encoding

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


_codecs = {}
_stdio = {}


def codec_register_alias(alias, name):
    """Register an alias for encoding 'name'."""
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
    """Decode text if not unicode."""
    if not isinstance(text, str):
        text = text.decode(encoding, errors)
    return text


def conditional_encode(text, encoding="UTF-8", errors="strict"):
    """Encode text if unicode."""
    if isinstance(text, str):
        text = text.encode(encoding, errors)
    return text


def encodestdio(encodings=None, errors=None):
    """Wrap sys.stdin, sys.stdout, and sys.stderr with EncodedStream.

    After this function is called, Unicode strings written to stdout/stderr are
    automatically encoded and strings read from stdin automatically decoded
    with the given encodings and error handling.

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
    """Read from stream.

    Uses os.read() if stream is a tty, stream.read() otherwise.
    """
    return os.read(stream.fileno(), size) if stream.isatty() else stream.read(size)


def write(stream, data):
    """Write to stream.

    Uses os.write() if stream is a tty, stream.write() otherwise.
    """
    if stream.isatty():
        os.write(stream.fileno(), data)
    else:
        stream.write(data)


class EncodedStream:
    """Automatically encodes writes and decodes reads using the given encoding.

    This class also does error handling. Uses os.read() and os.write() for
    proper handling of unicode codepages for stdout/stderr under Windows.
    """

    def __init__(self, stream, encoding="UTF-8", errors="strict"):
        self.stream = stream
        self.encoding = encoding
        self.errors = errors

    def __getattr__(self, name: str) -> Any:
        """Get attributes from the stream or the EncodedStream itself.

        Args:
            name (str): The name of the attribute to get.
        """
        return getattr(self.stream, name)

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the lines in the stream."""
        return iter(self.readlines())

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attributes on the stream or the EncodedStream itself.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        if name == "softspace":
            setattr(self.stream, name, value)
        else:
            object.__setattr__(self, name, value)

    def __next__(self):
        """Read the next line from the stream.

        Returns:
            str: The next line read from the stream, decoded.
        """
        return self.readline()

    def read(self, size=-1):
        """Read from the stream and decode it.

        Args:
            size (int): The number of bytes to read. Defaults to -1, which
                reads the entire stream.

        Returns:
            str: The decoded text read from the stream.
        """
        return conditional_decode(read(self.stream, size), self.encoding, self.errors)

    def readline(self, size=-1):
        """Read a single line from the stream and decode it.

        Args:
            size (int): The number of bytes to read. Defaults to -1, which
                reads the entire line.

        Returns:
            str: The decoded line read from the stream.
        """
        return conditional_decode(
            self.stream.readline(size), self.encoding, self.errors
        )

    def readlines(self, size=-1):
        """Read lines from the stream and decode them.

        Args:
            size (int): The number of bytes to read. Defaults to -1, which
                reads all lines.

        Returns:
            list: A list of decoded lines read from the stream.
        """
        return [
            conditional_decode(line, self.encoding, self.errors)
            for line in self.stream.readlines(size)
        ]

    def xreadlines(self) -> Self:
        """Return an iterator that reads lines from the stream.

        Returns:
            Iterator[str]: An iterator that yields lines from the stream.
        """
        return self

    def write(self, text):
        """Write text to the stream, encoding it if necessary.

        Args:
            text (str): The text to write to the stream.
        """
        write(self.stream, conditional_encode(text, self.encoding, self.errors))

    def writelines(self, lines):
        """Write a list of lines to the stream.

        Args:
            lines (list): A list of strings to write to the stream.
        """
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
    except (OSError, LookupError, UnicodeError) as exception:
        print(f"could not print {test!r}:", exception)
    print("wrapping stdout/stderr via encodestdio()")
    encodestdio()
    print(test)
    print("exiting normally")
