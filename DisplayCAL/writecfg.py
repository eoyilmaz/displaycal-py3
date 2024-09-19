from DisplayCAL.config import appbasename, cfg, config_sys, confighome, defaults, setcfg
from DisplayCAL.getcfg import getcfg
from DisplayCAL.util_io import StringIOu as StringIO


import configparser
import os
import sys


def writecfg(which="user", worker=None, module=None, options=(), cfg=cfg):
    """
    Write configuration file.

    which: 'user' or 'system'
    worker: worker instance if ``which == 'system'``
    """
    if module:
        cfgbasename = f"{appbasename}-{module}"
    else:
        cfgbasename = appbasename
    # Remove unknown options
    for name, _val in cfg.items(configparser.DEFAULTSECT):
        if name not in defaults:
            print("Removing unknown option:", name)
            setcfg(name, None)
    if which == "user":
        # user config - stores everything and overrides system-wide config
        cfgfilename = os.path.join(confighome, f"{cfgbasename}.ini")
        try:
            io = StringIO()
            cfg.write(io)
            io.seek(0)
            lines = io.read().strip("\n").split("\n")
            if options:
                optionlines = []
                for optionline in lines[1:]:
                    for option in options:
                        if optionline.startswith(option):
                            optionlines.append(optionline)
            else:
                optionlines = lines[1:]
            # Sorting works as long as config has only one section
            lines = lines[:1] + sorted(optionlines)
            cfgfile = open(cfgfilename, "wb")
            cfgfile.write((os.linesep.join(lines) + os.linesep).encode())
            cfgfile.close()
        except Exception as exception:
            print(
                "Warning - could not write user configuration file "
                f"'{cfgfilename}': {exception}"
            )
            return False
    else:
        # system-wide config - only stores essentials ie. Argyll directory              # noqa: SC100
        cfgfilename1 = os.path.join(confighome, f"{cfgbasename}.local.ini")
        cfgfilename2 = os.path.join(config_sys, f"{cfgbasename}.ini")
        if sys.platform == "win32":
            cfgfilename = cfgfilename2
        else:
            cfgfilename = cfgfilename1
        try:
            cfgfile = open(cfgfilename, "wb")
            if getcfg("argyll.dir"):
                cfgfile.write(
                    (
                        "%s%s"
                        % (
                            os.linesep.join(
                                [
                                    "[Default]",
                                    "%s = %s" % ("argyll.dir", getcfg("argyll.dir")),
                                ]
                            ),
                            os.linesep,
                        )
                    ).encode()
                )
            cfgfile.close()
            if sys.platform != "win32":
                # on Linux and OS X, we write the file to the user's config dir
                # then 'su mv' it to the system-wide config dir                         # noqa: SC100
                result = worker.exec_cmd(
                    "mv",
                    ["-f", cfgfilename1, cfgfilename2],
                    capture_output=True,
                    low_contrast=False,
                    skip_scripts=True,
                    silent=True,
                    asroot=True,
                )
                if isinstance(result, Exception):
                    raise result
        except Exception as exception:
            print(
                f"Warning - could not write system-wide configuration file '{cfgfilename2}': {exception}"
            )
            return False
    return True
