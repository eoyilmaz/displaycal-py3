#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
import os
import re
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import lazydict
from DisplayCAL.util_list import natsort
from DisplayCAL.util_os import listdir_re


USE_INLINE = False


def quote(obj):
    if isinstance(obj, str):
        return '"%s"' % obj.replace("\\", "\\\\").replace('"', '\\"').replace(
            "\n", "\\n"
        ).replace("\t", "\\t")
    else:
        return repr(obj)


def langmerge(infilename1, infilename2, outfilename):
    print("Syncing", infilename1, "to", infilename2)
    dictin1 = lazydict.LazyDict_YAML_UltraLite(infilename1)
    dictin1.load()
    dictin2 = lazydict.LazyDict_YAML_UltraLite(infilename2)
    dictin2.load()

    added = []
    same = []
    for key in dictin2:
        value = dictin2[key]
        if key not in dictin1:
            dictin1[key] = value
            added.append(key.encode("UTF-8"))
            if "*" + key not in dictin1:
                print("Added: '%s' '%s'" % (key, value))
        # elif dictin1[key] == value and not key.startswith("*") and not key.startswith("!") and value.strip():
        # same.append(key.encode("UTF-8"))
        # print("Same: '%s' '%s'" % (key, value))
        elif key != "*":
            # Check format chars
            format_chars = "dixXfFeEgGcs%"
            profile_name_placeholder_chars = "aAbBHIjmMpSUwWyY"
            for c in format_chars + profile_name_placeholder_chars:
                a = dictin1[key].count("%" + c)
                b = value.count("%" + c)
                if a != b:
                    print(
                        key,
                        "ERROR: Format character count for %%%s is wrong:" % c,
                        a,
                        "(expected %i)" % b,
                    )
            if key.startswith("info."):
                # Check tag formatting and correct Google translator messing
                # with tags
                original = dictin1[key]
                # Clean up whitespace
                # E.g. ' <font> ' -> ' <font>'
                wscleaned = re.sub(r"(^|\s+)(<[^/> ]+[^>]*>)\s+", r"\1\2", original)
                # E.g. 'x<font> ' -> 'x <font>'
                wscleaned = re.sub(r"([^>])(<[^/> ]+[^>]*>)(\s+)", r"\1\3\2", wscleaned)
                # E.g. ': </font>' -> ':</font> '
                wscleaned = re.sub(r"([:\-])(\s+)(</[^>]*>)\s*", r"\1\3\2", wscleaned)
                # E.g. ', </font>' -> '</font>, '
                wscleaned = re.sub(r"([,;.])(\s+)(</[^>]*>)\s*", r"\3\1\2", wscleaned)
                # E.g. ' </font> ' -> '</font> '
                wscleaned = re.sub(r"\s+(</[^>]*>\s+)", r"\1", wscleaned)
                # E.g. ' </font>x' -> '</font> x'
                wscleaned = re.sub(
                    r"(\s+)(</[^>]*>)([^<,;.:\- \n])", r"\2\1\3", wscleaned
                )
                if original != wscleaned:
                    print(key, "INFO: Corrected whitespace.")
                # Find all tags
                tags = re.findall(
                    r"<(\s*[^/> ]+)([^>]*)>([^<]*)(<\s*/\s*\1>)", wscleaned
                )
                replaced = wscleaned
                cleaned = wscleaned
                tagcleaned = wscleaned
                for tagname, attrs, contents, end in tags:
                    tag = "<%s%s>%s%s" % (tagname, attrs, contents, end)
                    replaced = replaced.replace(tag, contents)
                    # <font weight='bold'></font> is the only supported tag
                    cleaned = cleaned.replace(
                        tag, "<font weight='bold'>%s</font>" % contents.strip()
                    )
                    if contents != contents.strip():
                        print(
                            key,
                            "INFO: Removed surrounding whitespace from tag contents %s"
                            % tag,
                        )
                    tagcleaned = cleaned.replace(
                        tag, "<font weight='bold'>%s</font>" % contents
                    )
                stripped = re.sub(r"<[^>]*>", "", replaced)
                stripped = stripped.replace("<", "").replace(">", "")
                if replaced != stripped:
                    print(key, "ERROR: Invalid markup")
                if wscleaned != tagcleaned:
                    print(key, "INFO: Corrected tag formatting.")
                if original != cleaned:
                    dictin1[key] = cleaned

    merged = dict()
    merged["*"] = dictin1["*"] = dictin2["*"]

    for key in natsort(dictin2.keys(), False):
        merged[key] = dictin1[key]

    for key in natsort(dictin1.keys(), False):
        if key not in dictin2 and not key.startswith("*") and dictin1[key]:
            if "ORPHANED KEY-VALUE PAIRS" not in merged:
                merged[
                    "ORPHANED KEY-VALUE PAIRS"
                ] = "Note to translators: Key-value pairs below this point are no longer used. You may consider removing them."
            merged[key] = dictin1[key]
            print("Orphan: '%s' '%s'" % (key, dictin1[key]))

    outstream = BytesIO()
    for key in merged:
        value = merged[key]
        if not USE_INLINE or b"\n" in value:
            outstream.write(b'"%s": |-\n' % key.encode("UTF-8"))
            for line in value.split("\n"):
                # Do not use splitlines, returns empty list for empty string
                outstream.write(b"  %s\n" % line.encode("UTF-8"))
        else:
            # Inline
            outstream.write(
                b'"%s": "%s"\n'
                % (key.encode("UTF-8"), lazydict.escape(value).encode("UTF-8"))
            )
    outstream.seek(0)
    formatted = outstream.read()
    for key in added:
        formatted = formatted.replace(b'"%s":' % key, b'"*%s":' % key)
    for key in same:
        formatted = formatted.replace(b'"%s":' % key, b'"*%s":' % key)
    with open(dictin1.path, "rb") as infile:
        if infile.read() == formatted:
            print("no change")
            return
    print("writing", outfilename)
    with open(outfilename, "wb") as outfile:
        outfile.write(formatted)


if __name__ == "__main__":
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print("Usage: %s" % os.path.basename(sys.argv[0]))
        print("Synchronizes translations to en.yaml")
    else:
        for langfile in listdir_re(
            os.path.join(root, "DisplayCAL", "lang"), r"^\w+\.yaml$"
        ):
            if langfile != "template.yaml":
                langmerge(
                    os.path.join("lang", langfile),
                    os.path.join("lang", "en.yaml"),
                    os.path.join(root, "DisplayCAL", "lang", langfile),
                )
                print("")
