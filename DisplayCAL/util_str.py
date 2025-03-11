# -*- coding: utf-8 -*-

import codecs
import locale
import re
import string
import sys
import unicodedata
from functools import reduce

env_errors = (EnvironmentError,)
if sys.platform == "win32":
    import pywintypes

    env_errors = env_errors + (pywintypes.error, pywintypes.com_error)

from DisplayCAL.encoding import get_encodings

fs_enc = get_encodings()[1]

ascii_printable = "".join(
    [
        getattr(string, name)
        for name in ("digits", "ascii_letters", "punctuation", "whitespace")
    ]
)

# Control chars are defined as charcodes in the decimal range 0-31 (inclusive)
# except whitespace characters, plus charcode 127 (DEL)
control_chars = "".join(
    [chr(i) for i in list(range(0, 9)) + list(range(14, 32)) + [127]]
)

# Safe character substitution - can be used for filenames
# i.e. no \/:*?"<>| will be added through substitution
# Contains only chars that are not normalizable
safesubst = {
    # Latin-1 supplement
    "\u00a2": "c",  # Cent sign
    "\u00a3": "GBP",  # Pound sign
    "\u00a5": "JPY",  # Yen sign
    "\u00a9": "(C)",  # U+00A9 copyright sign
    "\u00ac": "!",  # Not sign
    "\u00ae": "(R)",  # U+00AE registered sign
    "\u00b0": "deg",  # Degree symbol
    "\u00b1": "+-",
    "\u00c4": "Ae",  # Capital letter A with diaresis (Umlaut)
    "\u00c5": "Aa",  # Capital letter A with ring above
    "\u00c6": "AE",
    "\u00d6": "Oe",  # Capital letter O with diaresis (Umlaut)
    "\u00dc": "Ue",  # Capital letter U with diaresis (Umlaut)
    "\u00d7": "x",  # U+00D7 multiplication sign
    "\u00df": "ss",
    "\u00e4": "ae",  # Small letter a with diaresis (Umlaut)
    "\u00e5": "aa",  # Small letter a with ring above
    "\u00e6": "ae",
    "\u00f6": "oe",  # Small letter o with diaresis (Umlaut)
    "\u00fc": "ue",  # Small letter u with diaresis (Umlaut)
    # Latin extended A
    "\u0152": "OE",
    "\u0153": "oe",
    # General punctuation
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",  # U+2013 en dash
    "\u2014": "--",  # U+2014 em dash
    "\u2015": "---",  # U+2015 horizontal bar
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": ",",
    "\u201b": "'",
    "\u201c": "''",
    "\u201d": "''",
    "\u201e": ",,",
    "\u201f": "''",
    "\u2032": "'",
    "\u2033": "''",
    "\u2034": "'''",
    "\u2035": "'",
    "\u2036": "''",
    "\u2037": "'''",
    "\u2053": "~",
    # Superscripts and subscripts
    "\u207b": "-",  # Superscript minus
    "\u208b": "-",  # Subscript minus
    # Currency symbols
    "\u20a1": "CRC",  # Costa Rica 'Colon'
    "\u20a6": "NGN",  # Nigeria 'Naira'
    "\u20a9": "KRW",  # South Korea 'Won'
    "\u20aa": "ILS",  # Isreael 'Sheqel'
    "\u20ab": "VND",  # Vietnam 'Dong'
    "\u20ac": "EUR",
    "\u20ad": "LAK",  # Laos 'Kip'
    "\u20ae": "MNT",  # Mongolia 'Tugrik'
    "\u20b2": "PYG",  # Paraguay 'Guarani'
    "\u20b4": "UAH",  # Ukraine 'Hryvnja'
    "\u20b5": "GHS",  # Ghana 'Cedi'
    "\u20b8": "KZT",  # Kasachstan 'Tenge'
    "\u20b9": "INR",  # Indian 'Rupee'
    "\u20ba": "TRY",  # Turkey 'Lira'
    "\u20bc": "AZN",  # Aserbaidchan 'Manat'
    "\u20bd": "RUB",  # Russia 'Ruble'
    "\u20be": "GEL",  # Georgia 'Lari'
    # Letter-like symbols
    "\u2117": "(P)",
    # Mathematical operators
    "\u2212": "-",  # U+2212 minus sign
    "\u2260": "!=",
    # Enclosed alphanumerics
    "\u2460": "(1)",
    "\u2461": "(2)",
    "\u2462": "(3)",
    "\u2463": "(4)",
    "\u2464": "(5)",
    "\u2465": "(6)",
    "\u2466": "(7)",
    "\u2467": "(8)",
    "\u2468": "(9)",
    "\u2469": "(10)",
    "\u246a": "(11)",
    "\u246b": "(12)",
    "\u246c": "(13)",
    "\u246d": "(14)",
    "\u246e": "(15)",
    "\u246f": "(16)",
    "\u2470": "(17)",
    "\u2471": "(18)",
    "\u2472": "(19)",
    "\u2473": "(20)",
    "\u24eb": "(11)",
    "\u24ec": "(12)",
    "\u24ed": "(13)",
    "\u24ee": "(14)",
    "\u24ef": "(15)",
    "\u24f0": "(16)",
    "\u24f1": "(17)",
    "\u24f2": "(18)",
    "\u24f3": "(19)",
    "\u24f4": "(20)",
    "\u24f5": "(1)",
    "\u24f6": "(2)",
    "\u24f7": "(3)",
    "\u24f8": "(4)",
    "\u24f9": "(5)",
    "\u24fa": "(6)",
    "\u24fb": "(7)",
    "\u24fc": "(8)",
    "\u24fd": "(9)",
    "\u24fe": "(10)",
    "\u24ff": "(0)",
    # Dingbats
    "\u2776": "(1)",
    "\u2777": "(2)",
    "\u2778": "(3)",
    "\u2779": "(4)",
    "\u277a": "(5)",
    "\u277b": "(6)",
    "\u277c": "(7)",
    "\u277d": "(8)",
    "\u277e": "(9)",
    "\u277f": "(10)",
    "\u2780": "(1)",
    "\u2781": "(2)",
    "\u2782": "(3)",
    "\u2783": "(4)",
    "\u2784": "(5)",
    "\u2785": "(6)",
    "\u2786": "(7)",
    "\u2787": "(8)",
    "\u2788": "(9)",
    "\u2789": "(10)",
    "\u278a": "(1)",
    "\u278b": "(2)",
    "\u278c": "(3)",
    "\u278d": "(4)",
    "\u278e": "(5)",
    "\u278f": "(6)",
    "\u2790": "(7)",
    "\u2791": "(8)",
    "\u2792": "(9)",
    "\u2793": "(10)",
}

# Extended character substitution - can NOT be used for filenames
# Contains only chars that are not normalizable
subst = dict(safesubst)
subst.update(
    {
        # Latin-1 supplement
        "\u00a6": "|",
        "\u00ab": "<<",
        "\u00bb": ">>",
        "\u00bc": "1/4",
        "\u00bd": "1/2",
        "\u00be": "3/4",
        "\u00f7": ":",
        # General punctuation
        "\u201c": '"',
        "\u201d": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2036": '"',
        "\u2039": "<",
        "\u203a": ">",
        "\u203d": "!?",
        "\u2044": "/",
        # Number forms
        "\u2153": "1/3",
        "\u2154": "2/3",
        "\u215b": "1/8",
        "\u215c": "3/8",
        "\u215d": "5/8",
        "\u215e": "7/8",
        # Arrows
        "\u2190": "<-",
        "\u2192": "->",
        "\u2194": "<->",
        # Mathematical operators
        "\u226a": "<<",
        "\u226b": ">>",
        "\u2264": "<=",
        "\u2265": "=>",
    }
)


class StrList(list):
    """It's a list. It's a string. It's a list of strings that behaves like a
    string! And like a list."""

    def __init__(self, seq=tuple()):
        list.__init__(self, seq)

    def __iadd__(self, text):
        self.append(text)
        return self

    def __getattr__(self, attr):
        return getattr(str(self), attr)

    def __str__(self):
        return "".join(self)


def asciize(obj):
    """Turn several unicode chars into an ASCII representation.

    This function either takes a string or an exception as argument (when used
    as error handler for encode or decode).
    """
    chars = b""
    if isinstance(obj, Exception):
        for char in obj.object[obj.start : obj.end]:
            chars += subst.get(char, normalencode(char).strip() or b"?")
        return chars, obj.end
    else:
        return obj.encode("ASCII", "asciize")


codecs.register_error("asciize", asciize)


def safe_asciize(obj) -> bytes:
    """Turn several unicode chars into an ASCII representation.

    This function either takes a string or an exception as argument (when used
    as error handler for encode or decode).
    """
    chars = b""
    if isinstance(obj, Exception):
        for char in obj.object[obj.start : obj.end]:
            if char in safesubst:
                subst_char = safesubst[char]
            else:
                subst_char = b"_"
                if char not in subst:
                    subst_char = normalencode(char).strip() or subst_char
            chars += subst_char
        return chars, obj.end
    elif isinstance(obj, str):
        return obj.encode("ASCII", "safe_asciize")
    elif isinstance(obj, bytes):
        return obj.decode("utf-8").encode("ASCII", "safe_asciize")


codecs.register_error("safe_asciize", safe_asciize)


def escape(obj):
    """Turn unicode chars into escape codes.

    This function either takes a string or an exception as argument (when used
    as error handler for encode or decode).

    """
    chars = b""
    if isinstance(obj, Exception):
        for char in obj.object[obj.start : obj.end]:
            chars += subst.get(char, "\\u%s" % hex(ord(char))[2:].rjust(4, "0"))
        return chars, obj.end
    else:
        return obj.encode("ASCII", "escape")


# TODO: convert this to a decorator
codecs.register_error("escape", escape)


def make_ascii_printable(text, substitute=b""):
    """Make ASCII printable.

    Args:
        text (bytes, str): A ``bytes`` or ``str`` value.
        substitute (bytes, str): A ``bytes`` or ``str`` value.

    Returns:
        bytes or str:
    """
    buffer = []
    joiner = ""
    temp_ascii_printable = ascii_printable
    if isinstance(text, bytes):
        joiner = b""
        temp_ascii_printable = ascii_printable.encode("utf-8")
        if isinstance(substitute, str):
            substitute = substitute.encode("utf-8")
    else:
        if isinstance(substitute, bytes):
            substitute = substitute.decode("utf-8")

    for i in range(len(text)):
        char = text[i : i + 1]
        if char in temp_ascii_printable:
            buffer.append(char)
        else:
            buffer.append(substitute)
    return joiner.join(buffer)


def make_filename_safe(unistr, encoding=fs_enc, substitute="_", concat=True):
    """Make sure string is safe to use as filename.

    I.e. turn characters that are invalid in the filesystem encoding into ASCII
    equivalents and replace characters that are invalid in filenames with
    substitution character.
    """
    if not isinstance(unistr, (str, bytes)):
        raise TypeError(
            "unistr should be a str or bytes, not {}".format(unistr.__class__.__name__)
        )
    # Turn characters that are invalid in the filesystem encoding into ASCII
    # substitution character '?'
    # NOTE that under Windows, encoding with the filesystem encoding may
    # substitute some characters even in "strict" replacement mode depending
    # on the Windows language setting for non-Unicode programs! (Python 2.x
    # under Windows supports Unicode by wrapping the win32 ASCII API, so it is
    # a non-Unicode program from that point of view. This problem presumably
    # doesn't exist with Python 3.x which uses the win32 Unicode API)
    if isinstance(unistr, str):
        # str
        unidec = unistr.encode(encoding, "replace").decode(encoding, "replace")
        pattern = r"[\\/:*?\"<>|]"
        plus = "+"
        uniout = ""
        question_mark = "?"
        if isinstance(substitute, bytes):
            substitute = substitute.decode(encoding)
    else:
        # bytes
        unidec = unistr.decode(encoding, "replace").encode(encoding, "replace")
        pattern = rb"[\\/:*?\"<>|]"
        plus = b"+"
        uniout = b""
        question_mark = b"?"
        if isinstance(substitute, str):
            substitute = substitute.encode(encoding)

    # Replace substitution character '?' with ASCII equivalent of original char
    for i in range(len(unidec)):
        c = unidec[i : i + 1]
        if c == question_mark:
            c = safe_asciize(unistr[i : i + 1])  # this will always be bytes
            if isinstance(unistr, str):
                c = c.decode(encoding)
        uniout += c
    # Remove invalid chars
    if concat:
        pattern += plus

    uniout = re.sub(pattern, substitute, uniout)
    return uniout


def normalencode(unistr, form="NFKD", encoding="ASCII", errors="ignore"):
    """Return encoded normal form of unicode string"""
    return unicodedata.normalize(form, unistr).encode(encoding, errors)


def box(text, width=80, collapse=False):
    """Create a box around text (monospaced font required for display)"""
    content_width = width - 4
    text = wrap(str(text), content_width)
    lines = text.splitlines()
    if collapse:
        content_width = 0
        for line in lines:
            content_width = max(len(line), content_width)
        width = content_width + 4
    horizontal_line = "\u2500" * (width - 2)
    box = ["\u250c%s\u2510" % horizontal_line]
    for line in lines:
        box.append("\u2502 %s \u2502" % line.ljust(content_width))
    box.append("\u2514%s\u2518" % horizontal_line)
    return "\n".join(box)


def center(text, width=None):
    """Center (mono-spaced) text.

    If no width is given, the longest line
    (after breaking at each newline) is used as max width.

    """
    text = text.split("\n")
    if width is None:
        width = 0
        for line in text:
            if len(line) > width:
                width = len(line)
    i = 0
    for line in text:
        text[i] = line.center(width)
        i += 1
    return "\n".join(text)


def create_replace_function(template, values):
    """Create a replace function for use with e.g. re.sub"""

    def replace_function(match, template=template, values=values):
        template = match.expand(template)
        return template % values

    return replace_function


def ellipsis_(text, maxlen=64, pos="r"):
    """Truncate text to maxlen characters and add ellipsis if it was longer.

    Ellipsis position can be 'm' (middle) or 'r' (right).
    """
    if len(text) <= maxlen:
        return text
    ellipsis_char = "\u2026"
    if isinstance(text, bytes):
        ellipsis_char = b"u\xc2\x826"
    if pos == "r":
        return text[: maxlen - 1] + ellipsis_char
    elif pos == "m":
        return text[: int(maxlen / 2)] + ellipsis_char + text[int(-maxlen / 2 + 1) :]


def hexunescape(match):
    """To be used with re.sub"""
    return chr(int(match.group(1), 16))


def indent(text, prefix, predicate=None):
    # From Python 3.7 textwrap module
    """Adds 'prefix' to the beginning of selected lines in 'text'.

    If 'predicate' is provided, 'prefix' will only be added to the lines
    where 'predicate(line)' is True. If 'predicate' is not provided,
    it will default to adding 'prefix' to all non-empty lines that do not
    consist solely of whitespace characters.
    """
    if predicate is None:

        def predicate(line):
            return line.strip()

    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if predicate(line) else line)

    return "".join(prefixed_lines())


def universal_newlines(txt):
    """Return txt with all new line formats converted to POSIX newlines."""
    if isinstance(txt, str):
        return txt.replace("\r\n", "\n").replace("\r", "\n")
    elif isinstance(txt, bytes):
        return txt.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def replace_control_chars(txt, replacement=" ", collapse=False):
    """Replace all control characters.

    Default replacement character is ' ' (space).
    If the 'collapse' keyword argument evaluates to True, consecutive
    replacement characters are collapsed to a single one.

    """
    txt = strtr(txt, dict(list(zip(control_chars, [replacement] * len(control_chars)))))
    if collapse:
        while replacement * 2 in txt:
            txt = txt.replace(replacement * 2, replacement)
    return txt


def safe_basestring(obj, enc="utf-8", errors="replace"):
    """Return a string or bytes representation of obj.

    Return obj if isinstance(obj, basestring). Otherwise, return unicode(obj),
    string(obj), or repr(obj), whichever succeeds first.
    """
    if isinstance(obj, env_errors):
        # Possible variations of environment-type errors:
        # - instance with 'errno', 'strerror', 'filename' and 'args' attributes
        #   (created by EnvironmentError with three arguments)
        #   NOTE: The 'args' attribute will contain only the first two arguments
        # - instance with 'errno', 'strerror' and 'args' attributes
        #   (created by EnvironmentError with two arguments)
        # - instance with just 'args' attribute
        #   (created by EnvironmentError with one or more than three arguments)
        # - urllib2.URLError with empty 'args' attribute but 'reason' and
        #   'filename' attributes
        # - pywintypes.error with 'funcname', 'message', 'strerror', 'winerror'
        #   and 'args' attributes
        if hasattr(obj, "reason"):
            if isinstance(obj.reason, str):
                obj.args = (obj.reason,)
            elif isinstance(obj.reason, bytes):
                obj.args = (str(obj.reason, enc, errors),)
            else:
                obj.args = obj.reason
        error = []
        if getattr(obj, "winerror", None) is not None:
            # pywintypes.error or WindowsError
            error.append("[Windows Error %s]" % obj.winerror)
        elif getattr(obj, "errno", None) is not None:
            error.append("[Errno %s]" % obj.errno)
        if getattr(obj, "strerror", None) is not None:
            if getattr(obj, "filename", None) is not None:
                error.append(obj.strerror.rstrip(":.") + ":")
            elif getattr(obj, "funcname", None) is not None:
                # pywintypes.error
                error.append(obj.funcname + ": " + obj.strerror)
            else:
                error.append(obj.strerror)
        if not error:
            error = list(obj.args)
        if getattr(obj, "filename", None) is not None:
            error.append(obj.filename)

        temp_error = []
        for arg in error:
            if isinstance(arg, str):
                temp_error.append(arg)
            elif isinstance(arg, bytes):
                temp_error.append(str(arg, enc, errors))
            else:
                temp_error.append(str(arg))
        error = temp_error
        obj = " ".join(error)
    elif isinstance(obj, KeyError) and obj.args:
        obj = "Key does not exist: " + repr(obj.args[0])
    oobj = obj
    if not isinstance(obj, str):
        try:
            obj = str(obj, enc, errors)
        except (UnicodeDecodeError, TypeError):
            obj = repr(obj)

    if isinstance(oobj, Exception) and not isinstance(oobj, Warning):
        module = getattr(oobj, "__module__", "")
        package = safe_basestring.__module__.split(".")[0]  # Our own package
        if not module.startswith(package + "."):
            clspth = ".".join([_f for _f in [module, oobj.__class__.__name__] if _f])
            if not obj.startswith(clspth + ":") and obj != clspth:
                obj = ": ".join([_f for _f in [clspth, obj] if _f])
    return obj


def safe_str(obj, enc=fs_enc, errors="replace"):
    """Return string representation of obj"""
    return safe_basestring(obj, enc=enc, errors=errors)


def strtr(txt, replacements):
    """String multi-replace, a bit like PHP's strtr.

    replacements can be a dict, a list or a string.
    If list or string, all matches are replaced with the empty string ("").

    """
    if hasattr(replacements, "items"):
        replacements = iter(replacements.items())
    elif isinstance(replacements, str):
        for srch in replacements:
            txt = txt.replace(srch, "")
    elif isinstance(replacements, bytes):
        for srch in replacements:
            txt = txt.replace(srch, b"")
        return txt
    for srch, sub in replacements:
        if isinstance(txt, bytes):
            if not isinstance(srch, bytes):
                srch = srch.encode("utf-8")
            if not isinstance(sub, bytes):
                sub = sub.encode("utf-8")
        elif isinstance(txt, str):
            if not isinstance(srch, str):
                srch = srch.decode("utf-8")
            if not isinstance(sub, str):
                sub = sub.decode("utf-8")
        txt = txt.replace(srch, sub)
    return txt


def wrap(text, width=70):
    """A word-wrap function that preserves existing line breaks and spaces.

    Expects that existing line breaks are posix newlines (\\n).

    """
    return reduce(
        lambda line, word, width=width: "%s%s%s"
        % (
            line,
            " \n"[
                (
                    len(line) - line.rfind("\n") - 1 + len(word.split("\n", 1)[0])
                    >= width
                )
            ],
            word,
        ),
        text.split(" "),
    )


def test():
    for k in subst:
        v = subst[k]
        print(k, v)


if __name__ == "__main__":
    test()
