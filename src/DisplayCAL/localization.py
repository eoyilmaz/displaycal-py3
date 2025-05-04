# -*- coding: utf-8 -*-

import os
import re

from DisplayCAL.config import data_dirs, defaults, getcfg, storage
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.lazydict import LazyDict_YAML_UltraLite
from DisplayCAL.options import debug_localization as debug
from DisplayCAL.util_os import expanduseru


def init(set_wx_locale=False):
    """Populate translation dict with found language strings and set locale.

    If set_wx_locale is True, set locale also for wxPython.

    """
    langdirs = []
    for dir_ in data_dirs:
        langdirs.append(os.path.join(dir_, "lang"))
    for langdir in langdirs:
        if os.path.exists(langdir) and os.path.isdir(langdir):
            try:
                langfiles = os.listdir(langdir)
            except Exception as exception:
                print(
                    "Warning - directory '%s' listing failed: %s" % (langdir, exception)
                )
            else:
                for filename in langfiles:
                    name, ext = os.path.splitext(filename)
                    if ext.lower() == ".yaml" and name.lower() not in ldict:
                        path = os.path.join(langdir, filename)
                        ldict[name.lower()] = LazyDict_YAML_UltraLite(path)
    if len(ldict) == 0:
        handle_error(
            UserWarning(
                "Warning: No language files found. The "
                "following places have been searched:\n{}".format("\n".join(langdirs))
            )
        )


def update_defaults():
    defaults.update(
        {
            "last_3dlut_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_archive_save_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_cal_path": os.path.join(storage, getstr("unnamed")),
            "last_cal_or_icc_path": os.path.join(storage, getstr("unnamed")),
            "last_colorimeter_ti3_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_testchart_export_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_filedialog_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_icc_path": os.path.join(storage, getstr("unnamed")),
            "last_reference_ti3_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_ti1_path": os.path.join(storage, getstr("unnamed")),
            "last_ti3_path": os.path.join(storage, getstr("unnamed")),
            "last_vrml_path": os.path.join(storage, getstr("unnamed")),
        }
    )


def getcode():
    """Get language code from config"""
    lcode = getcfg("lang")
    if lcode not in ldict:
        # fall back to default
        lcode = defaults["lang"]
    if lcode not in ldict:
        # fall back to english
        lcode = "en"
    return lcode


def getstr(id_str, strvars=None, lcode=None, default=None):
    """Get a translated string from the dictionary"""
    if not lcode:
        lcode = getcode()
    if lcode not in ldict or id_str not in ldict[lcode]:
        # fall back to english
        lcode = "en"
    if lcode in ldict and id_str in ldict[lcode]:
        lstr = ldict[lcode][id_str]
        if debug:
            if id_str not in usage or not isinstance(usage[id_str], int):
                usage[id_str] = 1
            else:
                usage[id_str] += 1
        if strvars is not None:
            if not isinstance(strvars, (list, tuple)):
                strvars = [strvars]
            fmt = re.findall(r"%\d?(?:\.\d+)?[deEfFgGiorsxX]", lstr)
            if len(fmt) == len(strvars):
                if not isinstance(strvars, list):
                    strvars = list(strvars)
                for i, s in enumerate(strvars):
                    if fmt[i].endswith("s"):
                        s = str(s)
                    elif not fmt[i].endswith("r"):
                        try:
                            if fmt[i][-1] in "dioxX":
                                s = int(s)
                            else:
                                s = float(s)
                        except (TypeError, ValueError):
                            s = 0
                    strvars[i] = s
                lstr %= tuple(strvars)
        return lstr
    else:
        if debug and id_str and not isinstance(id_str, str) and " " not in id_str:
            usage[id_str] = 0
        return default or id_str


def gettext(text):
    if not catalog and defaults["lang"] in ldict:
        for id_str in ldict[defaults["lang"]]:
            lstr = ldict[defaults["lang"]][id_str]
            catalog[lstr] = {}
            catalog[lstr].id_str = id_str
    lcode = getcode()
    if catalog and text in catalog and lcode not in catalog[text]:
        catalog[text][lcode] = ldict[lcode].get(catalog[text].id_str, text)
    return catalog.get(text, {}).get(lcode, text)


ldict = {}
catalog = {}


if debug:
    import atexit
    from DisplayCAL.config import confighome
    from DisplayCAL.jsondict import JSONDict

    usage = JSONDict()
    usage_path = os.path.join(confighome, "localization_usage.json")
    if os.path.isfile(usage_path):
        usage.path = usage_path

    def write_usage():
        global usage
        if not usage:
            return
        if os.path.isfile(usage_path):
            temp = JSONDict(usage_path)
            temp.load()
            temp.update(usage)
            usage = temp
        with open(usage_path, "wb") as usagefile:
            usagefile.write(b"{\n")
            for key, count in sorted(usage.items()):
                usagefile.write(b'\t"%s": %i,\n' % (key.encode("UTF-8"), count))
            usagefile.write(b"}")

    atexit.register(write_usage)
