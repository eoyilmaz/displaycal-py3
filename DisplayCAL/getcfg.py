from DisplayCAL.constants import (
    appbasename,
    cfg,
    defaults,
    is_ccxx_testchart,
    valid_ranges,
    valid_values,
)
from DisplayCAL.get_data_path import get_data_path
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.util_str import create_replace_function, strtr


import configparser
import os
import re
from decimal import Decimal


def getcfg(name, fallback=True, raw=False, cfg=cfg):
    """
    Get and return an option value from the configuration.

    If fallback evaluates to True and the option is not set, return its default value.
    """
    if name == "profile.name.expanded" and is_ccxx_testchart():
        name = "measurement.name.expanded"
    value = None
    hasdef = name in defaults
    if hasdef:
        defval = defaults[name]
        deftype = type(defval)

    if cfg.has_option(configparser.DEFAULTSECT, name):
        try:
            value = cfg.get(configparser.DEFAULTSECT, name)
        except UnicodeDecodeError:
            pass
        else:
            # Check for invalid types and return default if wrong type
            if raw:
                pass
            elif (
                (name != "trc" or value not in valid_values["trc"])
                and hasdef
                and deftype in (Decimal, int, float)
            ):
                try:
                    value = deftype(value)
                except ValueError:
                    value = defval
                else:
                    valid_range = valid_ranges.get(name)
                    if valid_range:
                        value = min(max(valid_range[0], value), valid_range[1])
                    elif name in valid_values and value not in valid_values[name]:
                        value = defval
            elif name.startswith("dimensions.measureframe"):
                try:
                    value = [max(0, float(n)) for n in value.split(",")]
                    if len(value) != 3:
                        raise ValueError()
                except ValueError:
                    value = defaults[name]
                else:
                    value[0] = min(value[0], 1)
                    value[1] = min(value[1], 1)
                    value[2] = min(value[2], 50)
                    value = ",".join([str(n) for n in value])
            elif name == "profile.quality" and getcfg("profile.type") in ("g", "G"):
                # default to high quality for gamma + matrix
                value = "h"
            elif name == "trc.type" and getcfg("trc") in valid_values["trc"]:
                value = "g"
            elif name in valid_values and value not in valid_values[name]:
                if debug:
                    print(f"Invalid config value for {name}: {value}", end=" ")
                value = None
            elif name == "copyright":
                # Make sure DisplayCAL and Argyll version are up-to-date                # noqa: SC100
                pattern = re.compile(
                    r"(%s(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*" % appname, re.I
                )
                repl = create_replace_function("\\1%s", version)
                value = re.sub(pattern, repl, value)
                if appbasename != appname:
                    pattern = re.compile(
                        r"(%s(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*" % appbasename,
                        re.I,
                    )
                    repl = create_replace_function("\\1%s", version)
                    value = re.sub(pattern, repl, value)
                pattern = re.compile(
                    r"(Argyll(?:\s*CMS)?)((?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*",
                    re.I,
                )
                if defval.split()[-1] != "CMS":
                    repl = create_replace_function("\\1\\2%s", defval.split()[-1])
                else:
                    repl = "\\1"
                value = re.sub(pattern, repl, value)
            elif name == "measurement_mode":
                # Map n and r measurement modes to canonical l and c
                # the inverse mapping happens per-instrument in
                # Worker.add_measurement_features().
                # That way we can have compatibility with old and current Argyll CMS    # noqa: SC100
                value = {"n": "l", "r": "c"}.get(value, value)
    if value is None:
        if hasdef and fallback:
            value = defval
            if debug > 1:
                print(name, "- falling back to", value)
        else:
            if debug and not hasdef:
                print("Warning - unknown option:", name)
    if raw:
        return value
    if (
        value
        and isinstance(value, str)
        and name.endswith("file")
        and name != "colorimeter_correction_matrix_file"
        and (name != "testchart.file" or value != "auto")
        and (not os.path.isabs(value) or not os.path.exists(value))
    ):
        # colorimeter_correction_matrix_file is special because it's not (only) a path  # noqa: SC100
        if debug:
            print(f"{name} does not exist: {value}", end=" ")
        # Normalize path (important, this turns altsep into sep under Windows)          # noqa: SC100
        value = os.path.normpath(value)
        # Check if this is a relative path covered by data_dirs                         # noqa: SC100
        if (
            value.split(os.path.sep)[-3:-2] == [appname] or not os.path.isabs(value)
        ) and (
            value.split(os.path.sep)[-2:-1] == ["presets"]
            or value.split(os.path.sep)[-2:-1] == ["ref"]
            or value.split(os.path.sep)[-2:-1] == ["ti1"]
        ):
            value = os.path.join(*value.split(os.path.sep)[-2:])
            value = get_data_path(value)
        elif hasdef:
            value = None
        if not value and hasdef:
            value = defval
        if debug > 1:
            print(name, "- falling back to", value)
    elif name in ("displays", "instruments"):
        if not value:
            return []
        value = [
            strtr(
                v,
                [
                    ("%{}".format(hex(ord(os.pathsep))[2:].upper()), os.pathsep),
                    ("%25", "%"),
                ],
            )
            for v in value.split(os.pathsep)
        ]
    return value
