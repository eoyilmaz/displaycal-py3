from DisplayCAL.config import appbasename, cfg, cfginited, config_sys, confighome, defaults, makecfgdir, setcfg
from DisplayCAL.getcfg import getcfg


import configparser
import os


def initcfg(module=None, cfg=cfg, force_load=False):
    """
    Initialize the configuration.

    Read in settings if the configuration file exists,
    else create the settings directory if nonexistent.
    """
    if module:
        cfgbasename = f"{appbasename}-{module}"
    else:
        cfgbasename = appbasename
    makecfgdir()
    if os.path.exists(confighome) and not os.path.exists(
        os.path.join(confighome, f"{cfgbasename}.ini")
    ):
        # Set default preset
        setcfg("calibration.file", defaults["calibration.file"], cfg=cfg)

    # Read cfg                                                                          # noqa: SC100
    cfgnames = [appbasename]
    if module:
        cfgnames.append(cfgbasename)
    else:
        cfgnames.extend(
            f"{appbasename}-{othermod}" for othermod in ("testchart-editor",)
        )

    cfgroots = [confighome]
    if module == "apply-profiles":
        cfgroots.append(config_sys)

    cfgfiles = []
    for cfgname in cfgnames:
        for cfgroot in cfgroots:
            cfgfile = os.path.join(cfgroot, f"{cfgname}.ini")
            if os.path.isfile(cfgfile):
                try:
                    mtime = os.stat(cfgfile).st_mtime
                except EnvironmentError as exception:
                    print(f"Warning - os.stat('{cfgfile}') failed: {exception}")
                last_checked = cfginited.get(cfgfile)
                if force_load or mtime != last_checked:
                    cfginited[cfgfile] = mtime
                    cfgfiles.append(cfgfile)
                    if force_load:
                        msg = "Force loading"
                    elif last_checked:
                        msg = "Reloading"
                    else:
                        msg = "Loading"
                    # logger.debug(msg, cfgfile)                                        # noqa: SC100
                    print(msg, cfgfile)
                # Make user config take precedence
                break
    if not cfgfiles:
        return
    if not module:
        # Make most recent file take precedence
        cfgfiles.sort(key=lambda cfgfile: cfginited.get(cfgfile))
    try:
        cfg.read(cfgfiles)
    # This won't raise an exception if the file does not exist,
    # only if it can't be parsed
    except Exception:
        print(f"Warning - could not parse configuration files:\n{cfgfiles}")
        # Fix Python 2.7 ConfigParser option values being lists instead of
        # strings in case of a ParsingError. http://bugs.python.org/issue24142
        all_sections = [configparser.DEFAULTSECT]
        all_sections.extend(cfg.sections())
        for section in all_sections:
            for name, val in cfg.items(section):
                if isinstance(val, list):
                    cfg.set(section, name, "\n".join(val))
    finally:
        if not module and not getcfg("calibration.ambient_viewcond_adjust"):
            # Reset to default
            setcfg("calibration.ambient_viewcond_adjust.lux", None, cfg=cfg)
