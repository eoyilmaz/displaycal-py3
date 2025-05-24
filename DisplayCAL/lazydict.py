"""This module provides classes and utilities for working with lazy-loading
dictionaries. Lazy dictionaries defer loading their contents from external
files (e.g., JSON or YAML) until accessed, improving performance and memory
usage for large datasets.
"""

import codecs
import json
import os
from collections.abc import Iterator
from typing import Any

from DisplayCAL.config import get_data_path
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.util_str import safe_str


def unquote(string, raise_exception=True):
    """Remove single or double quote at start and end of string and unescape
    escaped chars, YAML-style

    Unlike 'string'.strip("'"'"'), only removes the outermost quote pair.
    Raises ValueError on missing end quote if there is a start quote.

    """
    if len(string) > 1 and string[0] in "'\"":
        if string[-1] == string[0]:
            # NOTE: Order of unescapes is important to match YAML!
            string = unescape(string[1:-1])

        elif raise_exception:
            raise ValueError("Missing end quote while scanning quoted scalar")
    return string


def escape(string: str) -> bytes:
    """Backslash-escape special chars in string."""
    if isinstance(string, str):
        string = string.encode("string_escape")
    return string


def unescape(string: bytes) -> str:
    """Unescape escaped chars in string."""
    if isinstance(string, bytes):
        string = string.decode("string_escape")
    return string


class LazyDict(dict):
    """Lazy dictionary with key -> value mappings.

    The actual mappings are loaded from the source YAML file when they
    are accessed.
    """

    def __init__(self, path=None, encoding="UTF-8", errors="strict"):
        super().__init__()
        self._is_loaded = False
        self.path = path
        self.encoding = encoding
        self.errors = errors

    def __cmp__(self, other: Any) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__cmp__(other)

    def __contains__(self, key: Any) -> bool:
        """Check if the dictionary contains a key.

        Args:
            key (Any): The key to check. Any hashable object.

        Returns:
            bool: True if the key is in the dictionary, False otherwise.
        """
        self.load()
        return super().__contains__(key)

    def __delitem__(self, key: Any) -> None:
        """Delete a key from the dictionary.

        Args:
            key (Any): The key to delete. Any hashable object.
        """
        self.load()
        super().__delitem__(key)

    def __eq__(self, other: object) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__eq__(other)

    def __ge__(self, other: Any) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is greater than or equal to the
                other object, False otherwise.
        """
        self.load()
        return super().__ge__(other)

    def __getitem__(self, name: str) -> Any:
        """Get the value for a given key in the dictionary.

        Args:
            name (str): The key to get the value for.

        Returns:
            Any: The value associated with the key.
        """
        self.load()
        return super().__getitem__(name)

    def __gt__(self, other: Any) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is greater than the other object,
                False otherwise.
        """
        self.load()
        return super().__gt__(other)

    def __iter__(self) -> Iterator:
        """Return an iterator over the dictionary keys.

        Returns:
            Iterator: An iterator over the dictionary keys.
        """
        self.load()
        return super().__iter__()

    def __le__(self, other) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is less than or equal to the other
                object, False otherwise.
        """
        self.load()
        return super().__le__(other)

    def __len__(self) -> int:
        """Return the number of items in the dictionary.

        Returns:
            int: The number of items in the dictionary.
        """
        self.load()
        return super().__len__()

    def __lt__(self, other: Any) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is less than the other object,
                False otherwise.
        """
        self.load()
        return super().__lt__(other)

    def __ne__(self, other: object) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is not equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__ne__(other)

    def __repr__(self) -> str:
        """Return a string representation of the dictionary.

        Returns:
            str: A string representation of the dictionary.
        """
        self.load()
        return super().__repr__()

    def __setitem__(self, name: str, value: Any) -> None:
        """Set the value for a given key in the dictionary.

        Args:
            name (str): The key to set.
            value (Any): The value to set for the key.
        """
        self.load()
        super().__setitem__(name, value)

    def __sizeof__(self) -> int:
        """Return the size of the dictionary in bytes.

        Returns:
            int: The size of the dictionary in bytes.
        """
        self.load()
        return super().__sizeof__()

    def clear(self):
        if not self._is_loaded:
            self._is_loaded = True
        super().clear()

    def copy(self):
        self.load()
        return super().copy()

    def get(self, name, fallback=None):
        self.load()
        return super().get(name, fallback)

    def items(self):
        self.load()
        return super().items()

    def iteritems(self):
        self.load()
        return super().items()

    def iterkeys(self):
        self.load()
        return super().keys()

    def itervalues(self):
        self.load()
        return super().values()

    def keys(self):
        self.load()
        return super().keys()

    def load(self, path=None, encoding=None, errors=None, raise_exceptions=False):
        if self._is_loaded or (not path and not self.path):
            return

        self._is_loaded = True
        if not path:
            path = self.path
        if path and not os.path.isabs(path):
            path = get_data_path(path)
        if path and os.path.isfile(path):
            self.path = path
            if encoding:
                self.encoding = encoding
            if errors:
                self.errors = errors
        else:
            handle_error(UserWarning(f"Warning - file not found:\n\n{path}"), tb=False)
            return
        try:
            with codecs.open(path, "r", self.encoding, self.errors) as f:
                self.parse(f)
        except OSError as exception:
            if raise_exceptions:
                raise
            handle_error(exception)
        except Exception as exception:
            if raise_exceptions:
                raise
            handle_error(
                UserWarning(f"Error parsing file:\n\n{path}\n\n{exception}"),
                tb=False,
            )

    def parse(self, iterable):
        # Override this in subclass
        pass

    def pop(self, key, *args):
        self.load()
        return super().pop(key, *args)

    def popitem(self, name, value):
        self.load()
        return super().popitem(name, value)

    def setdefault(self, name, value=None):
        self.load()
        return super().setdefault(name, value)

    def update(self, other):
        self.load()
        super().update(other)

    def values(self):
        self.load()
        return super().values()


class LazyDictJSON(LazyDict):
    """JSON lazy dictionary."""

    def parse(self, fileobj):
        super().update(json.load(fileobj))


class LazyDictYAMLUltraLite(LazyDict):
    """'YAML Ultra Lite' lazy dictionary

    YAML Ultra Lite is a restricted subset of YAML. It only supports the
    following notations:

    Key: Value 1
    "Key 2": "Value 2"
    "Key 3": |-
      Value 3 Line 1
      Value 3 Line 2

    All values are treated as strings.

    Syntax checking is limited for speed.
    Parsing is around a factor of 20 to 30 faster than PyYAML,
    around 8 times faster than JSONDict (based on demjson),
    and about 2 times faster than YAML_Lite.

    """

    def __init__(self, path=None, encoding="UTF-8", errors="strict", debug=False):
        super().__init__(path, encoding, errors)
        self.debug = debug

    def parse(self, fileobj):
        """Parse fileobj and update dict"""
        block = False
        value = []
        key = None
        # Readlines is actually MUCH faster than iterating over the
        # file object
        for i, line in enumerate(fileobj.readlines(), 1):
            line = line.replace("\r\n", "\n")
            if line.lstrip(" ").startswith("#"):
                # Ignore comments
                pass
            elif line != "\n" and not line.startswith("  "):
                if value:
                    self[key] = "".join(value).rstrip("\n")
                # tokens = line.rstrip(' -|\n').split(":", 1)
                tokens = line.split(":", 1)
                if len(tokens) == 1:
                    raise ValueError(
                        "Unsupported format ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                # key = tokens[0].strip("'"'"')
                key = self._unquote(tokens[0].strip(), False, False, fileobj, i)
                token = tokens[1].strip(" \n")
                if token.startswith("|-"):
                    block = True
                    token = token[2:].lstrip(" ")
                    if token:
                        if token.startswith("#"):
                            value = []
                            continue
                        raise ValueError(
                            "Expected a comment or a line break ({} line {})".format(
                                format(safe_str(getattr(fileobj, "name", line))), i
                            )
                        )
                elif token.startswith(("|", ">")):
                    raise ValueError(
                        "Style not supported ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                elif token.startswith("\t"):
                    raise ValueError(
                        "Found character '\\t' that cannot "
                        "start any token ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                if token:
                    # Inline value
                    block = False
                    if token.startswith("#"):
                        value = []
                        continue
                    comment_offset = token.find("#")
                    if (
                        comment_offset > -1
                        and token[comment_offset - 1 : comment_offset] == " "
                    ):
                        token = token[:comment_offset].rstrip(" \n")
                        if not token:
                            value = []
                            continue
                    # value = [token.strip("'"'"')]
                    value = [self._unquote(token, True, True, fileobj, i)]
                else:
                    value = []
            else:
                if not block:
                    raise ValueError(
                        "Unsupported format ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                value.append(line[2:])
        if key:
            self[key] = "".join(value).rstrip("\n")

    def _unquote(self, token, do_unescape=True, check=False, fileobj=None, lineno=-1):
        if len(token) <= 1:
            return token
        c = token[0]
        if c in "'\"" and c == token[-1]:
            token = token[1:-1]
            if check and token.count(c) != token.count("\\" + c):
                raise ValueError(
                    "Unescaped quotes found in token ({!r} line {})".format(
                        safe_str(getattr(fileobj, "name", token)), lineno
                    )
                )
            if do_unescape:
                token = unescape(token)
        elif check and (token.count('"') != token.count('\\"')):
            raise ValueError(
                "Unbalanced quotes found in token ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", token)), lineno
                )
            )
        if check and "\\'" in token:
            raise ValueError(
                'Found unknown escape character "\'" ({!r} line {})'.format(
                    safe_str(getattr(fileobj, "name", token)), lineno
                )
            )
        return token


class LazyDictYAMLLite(LazyDictYAMLUltraLite):
    """'YAML Lite' lazy dictionary

    YAML Lite is a restricted subset of YAML. It only supports the
    following notations:

    Key: Value 1
    "Key 2": "Value 2"
    "Key 3": |-
      Value 3 Line 1
      Value 3 Line 2
    "Key 4": |
      Value 4 Line 1
      Value 4 Line 2
    "Key 5": Folded value 5
      Folded value 5, continued

    All values are treated as strings.

    Syntax checking is limited for speed.
    Parsing is around a factor of 12 to 16 faster than PyYAML,
    and around 4 times faster than JSONDict (based on demjson).

    """

    def parse(self, fileobj):
        """Parse fileobj and update dict"""
        style = None
        value = []
        block_styles = ("|", ">", "|-", ">-", "|+", ">+")
        quote = None
        key = None
        # Readlines is actually MUCH faster than iterating over the
        # file object
        for i, line in enumerate(fileobj.readlines(), 1):
            line = line.replace("\r\n", "\n")
            line_lwstrip = line.lstrip(" ")
            if quote:
                line_rstrip = line.rstrip()
            if self.debug:
                print("LINE", repr(line))
            if not quote and style not in block_styles and line_lwstrip.startswith("#"):
                # Ignore comments
                pass
            elif quote and line_rstrip and line_rstrip[-1] == quote:
                if self.debug:
                    print("END QUOTE")
                    print("+ APPEND STRIPPED", repr(line.strip()))
                value.append(line.strip())
                self._collect(key, value, ">i")
                style = None
                value = []
                quote = None
                key = None
            elif (
                style not in block_styles
                and line.startswith(" ")
                and line_lwstrip
                and line_lwstrip[0] in ("'", '"')
            ):
                if quote:
                    raise ValueError(
                        "Wrong end quote while scanning quoted "
                        "scalar ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                if self.debug:
                    print("START QUOTE")
                quote = line_lwstrip[0]
                if self.debug:
                    print("+ APPEND LWSTRIPPED", repr(line_lwstrip))
                value.append(line_lwstrip)
            elif line.startswith("  ") and (
                style in block_styles or line_lwstrip != "\n"
            ):
                if style == ">i":
                    if not quote and "\t" in line:
                        raise ValueError(
                            "Found character '\\t' that cannot "
                            "start any token ({!r} line {})".format(
                                safe_str(getattr(fileobj, "name", line)), i
                            )
                        )
                    line = line.strip() + "\n"
                    if self.debug:
                        print("APPEND STRIPPED + \\n", repr(line))
                else:
                    line = line[2:]
                    if self.debug:
                        print("APPEND [2:]", repr(line))
                value.append(line)
            elif not quote and line_lwstrip != "\n" and not line.startswith(" "):
                if key and value:
                    self._collect(key, value, style)
                tokens = line.split(":", 1)
                key = unquote(tokens[0].strip())
                if len(tokens) > 1:
                    token = tokens[1].lstrip(" ").rstrip(" \n")
                    if token.startswith(("|", ">")):
                        if token[1:2] in "+-":
                            style = token[:2]
                            token = token[2:].lstrip(" ")
                        else:
                            style = token[:1]
                            token = token[1:].lstrip(" ")
                    else:
                        style = ""
                    if token.startswith("\t"):
                        raise ValueError(
                            "Found character '\\t' that cannot "
                            "start any token ({!r} line {})".format(
                                safe_str(getattr(fileobj, "name", line)), i
                            )
                        )
                    if style.startswith(">"):
                        raise NotImplementedError(
                            "Folded style is not supported ({!r} line {})".format(
                                safe_str(getattr(fileobj, "name", line)), i
                            )
                        )
                    if token.startswith("#"):
                        # Block or folded
                        if self.debug:
                            print("IN BLOCK", repr(key), style)
                        value = []
                        continue
                    if style and token:
                        raise ValueError(
                            "Expected a comment or a line break ({!r} line {})".format(
                                safe_str(getattr(fileobj, "name", line)), i
                            )
                        )
                else:
                    raise ValueError(
                        "Unsupported format ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                if style or not token:
                    # Block or folded
                    if self.debug:
                        print("IN BLOCK", repr(key), style)
                    value = []
                else:
                    # Inline value
                    if self.debug:
                        print("IN PLAIN", repr(key), repr(token))
                    style = None
                    if token.startswith("#"):
                        value = []
                        continue
                    token_rstrip = token.rstrip()
                    if (
                        token_rstrip
                        and token_rstrip[0] in ("'", '"')
                        and (
                            len(token_rstrip) < 2 or token_rstrip[0] != token_rstrip[-1]
                        )
                    ):
                        if self.debug:
                            print("START QUOTE")
                        quote = token_rstrip[0]
                    else:
                        style = ">i"
                        comment_offset = token_rstrip.find("#")
                        if (
                            comment_offset > -1
                            and token_rstrip[comment_offset - 1 : comment_offset] == " "
                        ):
                            token_rstrip = token_rstrip[:comment_offset].rstrip()
                    token_rstrip += "\n"
                    if self.debug:
                        print("SET", repr(token_rstrip))
                    value = [token_rstrip]
            else:
                # if line_lwstrip == "\n":
                if True:
                    if self.debug:
                        print("APPEND LWSTRIPPED", repr(line_lwstrip))
                    line = line_lwstrip
                elif self.debug:
                    print("APPEND", repr(line))
                value.append(line)
        if quote:
            raise ValueError(
                "EOF while scanning quoted scalar ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        if key:
            if self.debug:
                print("FINAL COLLECT")
            self._collect(key, value, style)

    def _collect(self, key, value, style=None):
        if self.debug:
            print("COLLECT", key, value, style)
        chars = "".join(value)
        if style != ">i":
            chars = chars.rstrip(" ")
        if not style or style.startswith(">"):
            if self.debug:
                print("FOLD")
            out = ""
            state = 0
            for c in chars:
                # print(repr(c), repr(state))
                if c == "\n":
                    if state > 0:
                        out += c
                    state += 1
                else:
                    if state == 1:
                        out += " "
                        state = 0
                    if style == ">i":
                        state = 0
                    out += c
        else:
            out = chars
        out = out.lstrip(" ")
        if self.debug:
            print("OUT", repr(out))
        if not style:
            # Inline value
            out = out.rstrip()
        elif style.endswith("+"):
            # Keep trailing newlines
            if self.debug:
                print("KEEP")
        else:
            out = out.rstrip("\n")
            if style == ">i":
                out = unquote(out)
            elif style.endswith("-"):
                # Chomp trailing newlines
                if self.debug:
                    print("CHOMP")
            else:
                # Clip trailing newlines (default)
                if self.debug:
                    print("CLIP")
                if chars.endswith("\n"):
                    out += "\n"
        self[key] = out
