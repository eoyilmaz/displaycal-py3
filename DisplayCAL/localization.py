import os
import re

from DisplayCAL.config import DATA_DIRS, DEFAULTS, STORAGE, getcfg
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.lazydict import LazyDictYAMLUltraLite
from DisplayCAL.options import DEBUG_LOCALIZATION as DEBUG
from DisplayCAL.util_os import expanduseru


def init(set_wx_locale=False):
    """Populate translation dict with found language strings and set locale.

    If set_wx_locale is True, set locale also for wxPython.

    """
    langdirs = []
    for dir_ in DATA_DIRS:
        langdirs.append(os.path.join(dir_, "lang"))
    for langdir in langdirs:
        if os.path.exists(langdir) and os.path.isdir(langdir):
            try:
                langfiles = os.listdir(langdir)
            except Exception as exception:
                print(f"Warning - directory '{langdir}' listing failed: {exception}")
            else:
                for filename in langfiles:
                    name, ext = os.path.splitext(filename)
                    if ext.lower() == ".yaml" and name.lower() not in LDICT:
                        path = os.path.join(langdir, filename)
                        LDICT[name.lower()] = LazyDictYAMLUltraLite(path)
    if len(LDICT) == 0:
        handle_error(
            UserWarning(
                "Warning: No language files found. The "
                "following places have been searched:\n{}".format("\n".join(langdirs))
            )
        )


def update_defaults():
    DEFAULTS.update(
        {
            "last_3dlut_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_archive_save_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_cal_path": os.path.join(STORAGE, getstr("unnamed")),
            "last_cal_or_icc_path": os.path.join(STORAGE, getstr("unnamed")),
            "last_colorimeter_ti3_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_testchart_export_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_filedialog_path": os.path.join(expanduseru("~"), getstr("unnamed")),
            "last_icc_path": os.path.join(STORAGE, getstr("unnamed")),
            "last_reference_ti3_path": os.path.join(
                expanduseru("~"), getstr("unnamed")
            ),
            "last_ti1_path": os.path.join(STORAGE, getstr("unnamed")),
            "last_ti3_path": os.path.join(STORAGE, getstr("unnamed")),
            "last_vrml_path": os.path.join(STORAGE, getstr("unnamed")),
        }
    )


def getcode():
    """Get language code from config"""
    lcode = getcfg("lang")
    if lcode not in LDICT:
        # fall back to default
        lcode = DEFAULTS["lang"]
    if lcode not in LDICT:
        # fall back to english
        lcode = "en"
    return lcode


def getstr(id_str, strvars=None, lcode=None, default=None):
    """Get a translated string from the dictionary"""
    if not lcode:
        lcode = getcode()
    if lcode not in LDICT or id_str not in LDICT[lcode]:
        # fall back to english
        lcode = "en"
    if lcode in LDICT and id_str in LDICT[lcode]:
        lstr = LDICT[lcode][id_str]
        if DEBUG:
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
                            s = int(s) if fmt[i][-1] in "dioxX" else float(s)
                        except (TypeError, ValueError):
                            s = 0
                    strvars[i] = s
                lstr %= tuple(strvars)
        return lstr
    if DEBUG and id_str and not isinstance(id_str, str) and " " not in id_str:
        usage[id_str] = 0
    return default or id_str


def gettext(text):
    if not CATALOG and DEFAULTS["lang"] in LDICT:
        for id_str in LDICT[DEFAULTS["lang"]]:
            lstr = LDICT[DEFAULTS["lang"]][id_str]
            CATALOG[lstr] = {}
            CATALOG[lstr].id_str = id_str
    lcode = getcode()
    if CATALOG and text in CATALOG and lcode not in CATALOG[text]:
        CATALOG[text][lcode] = LDICT[lcode].get(CATALOG[text].id_str, text)
    return CATALOG.get(text, {}).get(lcode, text)


LDICT = {}
CATALOG = {}


if DEBUG:
    import atexit

    from DisplayCAL.config import CONFIG_HOME
    from DisplayCAL.jsondict import JSONDict

    usage = JSONDict()
    usage_path = os.path.join(CONFIG_HOME, "localization_usage.json")
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
