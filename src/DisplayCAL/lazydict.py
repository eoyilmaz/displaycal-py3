# -*- coding: utf-8 -*-
import codecs
import json
import os
import traceback

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


def escape(string):
    r"""
    Backslash-escape special chars in string

    """
    return string.encode("string_escape")


def unescape(string):
    r"""
    Unescape escaped chars in string

    """
    return string.decode("string_escape")


class LazyDict(dict):
    """Lazy dictionary with key -> value mappings.

    The actual mappings are loaded from the source YAML file when they
    are accessed.

    """

    def __init__(self, path=None, encoding="UTF-8", errors="strict"):
        dict.__init__(self)
        self._isloaded = False
        self.path = path
        self.encoding = encoding
        self.errors = errors

    def __cmp__(self, other):
        self.load()
        return dict.__cmp__(self, other)

    def __contains__(self, key):
        self.load()
        return dict.__contains__(self, key)

    def __delitem__(self, key):
        self.load()
        dict.__delitem__(self, key)

    def __delslice__(self, i, j):
        self.load()
        dict.__delslice__(self, i, j)

    def __eq__(self, other):
        self.load()
        return dict.__eq__(self, other)

    def __ge__(self, other):
        self.load()
        return dict.__ge__(self, other)

    def __getitem__(self, name):
        self.load()
        return dict.__getitem__(self, name)

    def __getslice__(self, i, j):
        self.load()
        return dict.__getslice__(self, i, j)

    def __gt__(self, other):
        self.load()
        return dict.__gt__(self, other)

    def __iter__(self):
        self.load()
        return dict.__iter__(self)

    def __le__(self, other):
        self.load()
        return dict.__le__(self, other)

    def __len__(self):
        self.load()
        return dict.__len__(self)

    def __lt__(self, other):
        self.load()
        return dict.__lt__(self, other)

    def __ne__(self, other):
        self.load()
        return dict.__ne__(self, other)

    def __repr__(self):
        self.load()
        return dict.__repr__(self)

    def __setitem__(self, name, value):
        self.load()
        dict.__setitem__(self, name, value)

    def __sizeof__(self):
        self.load()
        return dict.__sizeof__(self)

    def clear(self):
        if not self._isloaded:
            self._isloaded = True
        dict.clear(self)

    def copy(self):
        self.load()
        return dict.copy(self)

    def get(self, name, fallback=None):
        self.load()
        return dict.get(self, name, fallback)

    def items(self):
        self.load()
        return dict.items(self)

    def iteritems(self):
        self.load()
        return dict.items(self)

    def iterkeys(self):
        self.load()
        return dict.keys(self)

    def itervalues(self):
        self.load()
        return dict.values(self)

    def keys(self):
        self.load()
        return dict.keys(self)

    def load(self, path=None, encoding=None, errors=None, raise_exceptions=False):
        if not self._isloaded and (path or self.path):
            self._isloaded = True
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
                handle_error(
                    UserWarning("Warning - file not found:\n\n%s" % path), tb=False
                )
                return
            try:
                with codecs.open(path, "r", self.encoding, self.errors) as f:
                    self.parse(f)
            except EnvironmentError as exception:
                if raise_exceptions:
                    raise
                handle_error(exception)
            except Exception as exception:
                if raise_exceptions:
                    raise
                handle_error(
                    UserWarning("Error parsing file:\n\n%s\n\n%s" % (path, exception)),
                    tb=False,
                )

    def parse(self, iterable):
        # Override this in subclass
        pass

    def pop(self, key, *args):
        self.load()
        return dict.pop(self, key, *args)

    def popitem(self, name, value):
        self.load()
        return dict.popitem(self, name, value)

    def setdefault(self, name, value=None):
        self.load()
        return dict.setdefault(self, name, value)

    def update(self, other):
        self.load()
        dict.update(self, other)

    def values(self):
        self.load()
        return dict.values(self)


class LazyDict_JSON(LazyDict):
    """JSON lazy dictionary"""

    def parse(self, fileobj):
        dict.update(self, json.load(fileobj))


class LazyDict_YAML_UltraLite(LazyDict):
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
        LazyDict.__init__(self, path, encoding, errors)
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
                        "Unsupported format (%r line %i)"
                        % (safe_str(getattr(fileobj, "name", line)), i)
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
                            "Expected a comment or a line break "
                            "(%r line %i)"
                            % (safe_str(getattr(fileobj, "name", line)), i)
                        )
                elif token.startswith("|") or token.startswith(">"):
                    raise ValueError(
                        "Style not supported "
                        "(%r line %i)" % (safe_str(getattr(fileobj, "name", line)), i)
                    )
                elif token.startswith("\t"):
                    raise ValueError(
                        "Found character '\\t' that cannot "
                        "start any token (%r line %i)"
                        % (safe_str(getattr(fileobj, "name", line)), i)
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
                        "Unsupported format (%r line %i)"
                        % (safe_str(getattr(fileobj, "name", line)), i)
                    )
                value.append(line[2:])
        if key:
            self[key] = "".join(value).rstrip("\n")

    def _unquote(self, token, do_unescape=True, check=False, fileobj=None, lineno=-1):
        if len(token) > 1:
            c = token[0]
            if c in "'\"" and c == token[-1]:
                token = token[1:-1]
                if check and token.count(c) != token.count("\\" + c):
                    raise ValueError(
                        "Unescaped quotes found in token "
                        "(%r line %i)"
                        % (safe_str(getattr(fileobj, "name", token)), lineno)
                    )
                if do_unescape:
                    token = unescape(token)
            elif check and (token.count('"') != token.count('\\"')):
                raise ValueError(
                    "Unbalanced quotes found in token "
                    "(%r line %i)" % (safe_str(getattr(fileobj, "name", token)), lineno)
                )
            if check and "\\'" in token:
                raise ValueError(
                    'Found unknown escape character "\'" '
                    "(%r line %i)" % (safe_str(getattr(fileobj, "name", token)), lineno)
                )
        return token


class LazyDict_YAML_Lite(LazyDict_YAML_UltraLite):
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
                if self.debug:
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
                        "scalar (%r line %i)"
                        % (safe_str(getattr(fileobj, "name", line)), i)
                    )
                else:
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
                            "start any token (%r line %i)"
                            % (safe_str(getattr(fileobj, "name", line)), i)
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
                    if token.startswith("|") or token.startswith(">"):
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
                            "start any token (%r line %i)"
                            % (safe_str(getattr(fileobj, "name", line)), i)
                        )
                    if style.startswith(">"):
                        raise NotImplementedError(
                            "Folded style is not "
                            "supported (%r line %i)"
                            % (safe_str(getattr(fileobj, "name", line)), i)
                        )
                    if token.startswith("#"):
                        # Block or folded
                        if self.debug:
                            print("IN BLOCK", repr(key), style)
                        value = []
                        continue
                    if style and token:
                        raise ValueError(
                            "Expected a comment or a line break "
                            "(%r line %i)"
                            % (safe_str(getattr(fileobj, "name", line)), i)
                        )
                else:
                    raise ValueError(
                        "Unsupported format (%r line %i)"
                        % (safe_str(getattr(fileobj, "name", line)), i)
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
                else:
                    if self.debug:
                        print("APPEND", repr(line))
                value.append(line)
        if quote:
            raise ValueError(
                "EOF while scanning quoted scalar (%r line %i)"
                % (safe_str(getattr(fileobj, "name", line)), i)
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
                # print repr(c), repr(state)
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
            pass
        else:
            out = out.rstrip("\n")
            if style == ">i":
                out = unquote(out)
            elif style.endswith("-"):
                # Chomp trailing newlines
                if self.debug:
                    print("CHOMP")
                pass
            else:
                # Clip trailing newlines (default)
                if self.debug:
                    print("CLIP")
                if chars.endswith("\n"):
                    out += "\n"
        self[key] = out


def test():
    from io import StringIO
    from time import time

    from DisplayCAL.jsondict import JSONDict

    # PyYAML
    import yaml
    from yaml import CSafeLoader

    def y(doc):
        try:
            return yaml.safe_load(StringIO(doc))
        except Exception as e:
            print(f"{e.__class__.__name__}:", e)
            traceback.print_exc()
            return e

    def l(doc):
        l = LazyDict_YAML_Lite(debug=True)
        try:
            l.parse(StringIO(doc))
        except Exception as e:
            print(f"{e.__class__.__name__}:", e)
            traceback.print_exc()
            return e
        return l

    def c(doc, do_assert=True):
        print("-" * 80)
        print(repr(doc))
        a = l(doc)
        print("LazyDict_YAML_Lite", a)
        b = y(doc)
        print("yaml.YAML         ", b)
        identical = isinstance(a, dict) and isinstance(b, dict) and a == b
        print("Identical?", identical)
        if do_assert:
            assert identical

    print("Testing YAML Lite to YAML conformance")
    c('TEST: \n  "ABC\n\n  DEF\n"  \n    \n\n\n\n')
    c('TEST: \n  "ABC\n\n  DEF"')
    c('TEST: \n  "ABC\n  DEF\n"')
    c('TEST: \n  "ABC\n\n  DEF\tG\n  \n    \n\n\n\n \t"')
    c("TEST: \n  ABC\n\n  DEFG\n  \n    \n\n\n\n")
    c('TEST: \n  "ABC\n\n  DEF\n"')
    c("TEST: \n  ABC\n\n DEFG\n  \n    \n\n\n\n ")
    c('TEST: \n  "ABC\n\n DEF\tG\n  \n    \n\n\n\n" ')
    c("TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n")
    c("TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n")
    c("TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n")
    # c('TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
    # c('TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
    # c('TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
    c('TEST: "\n ABC\n\n  DEFG\n  \n    \n\n\n\n"')
    c("TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    c("TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    c("TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    # c('TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
    # c('TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
    # c('TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
    c('TEST : |\n  "\n  ABC\n\n  DEFG\n  \n    \n\n\n\n  "')
    c("TEST: |-\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    c("TEST: |\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    c("TEST:\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ")
    c("TEST: |- # Comment\n  Value")
    c("TEST: |- # Comment\n  Value # Not A Comment\n  # Not A Comment")

    c("TEST: # Comment", do_assert=False)

    print("=" * 80)
    print("Performance test")

    io = StringIO(
        """{"test1": "Value 1",
"test2": "Value 2 Line 1\\nValue 2 Line 2\\n\\nValue 2 Line 4\\n",
"test3": "Value 3 Line 1\\n",
"test4": "Value 4"}
"""
    )

    d = JSONDict()
    ts = time()
    for i in range(10000):
        d.parse(io)
        io.seek(0)
    jt = time() - ts

    d = LazyDict_JSON()
    ts = time()
    for i in range(10000):
        d.parse(io)
        io.seek(0)
    ljt = time() - ts

    io = StringIO(
        """"test1": Value 1
"test2": |-
  Value 2 Line 1
  Value 2 Line 2

  Value 2 Line 4
"test3": |-
  Value 3 Line 1
"test4": "Value 4"
"""
    )

    d = LazyDict_YAML_UltraLite()
    ts = time()
    for i in range(10000):
        d.parse(io)
        io.seek(0)
    yult = time() - ts

    d = LazyDict_YAML_Lite()
    ts = time()
    for i in range(10000):
        d.parse(io)
        io.seek(0)
    ylt = time() - ts

    ts = time()
    for i in range(10000):
        yaml.safe_load(io)
        io.seek(0)
    yt = time() - ts

    ts = time()
    for i in range(10000):
        yaml.load(io, Loader=CSafeLoader)
        io.seek(0)
    yct = time() - ts

    print("JSONDict(demjson): %.3fs" % jt)
    print("LazyDict_JSON: %.3fs" % ljt)
    print(
        "LazyDict_YAML_UltraLite: %.3fs," % yult,
        "vs JSONDict: %.1fx speed," % round(jt / yult, 1),
        "vs YAML_Lite: %.1fx speed," % round(ylt / yult, 1),
        "vs PyYAML: %.1fx speed," % round(yt / yult, 1),
    )
    print(
        "LazyDict_YAML_Lite: %.3fs," % ylt,
        "vs JSONDict: %.1fx speed," % round(jt / ylt, 1),
        "vs PyYAML: %.1fx speed," % round(yt / ylt, 1),
    )
    print("yaml.safe_load: %.3fs" % yt)
    print("yaml.load(CSafeLoader): %.3fs" % yct)


if __name__ == "__main__":
    test()
