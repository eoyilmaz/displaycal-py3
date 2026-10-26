import configparser
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from DisplayCAL import config


def test_default_values_1():
    """Test default values of module level variables."""
    from DisplayCAL import config

    config.initcfg()

    assert config.configparser.DEFAULTSECT == "Default"
    assert sys.executable == config.EXE  # venv/bin/python
    assert os.path.dirname(sys.executable) == config.EXEDIR  # venv/bin
    assert os.path.basename(sys.executable) == config.EXENAME  # python
    assert config.ISEXE is False
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.PYFILE != ""
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.PYPATH != ""
    assert config.ISAPP is False
    assert config.PYNAME != ""  # _jb_pytest_runner
    # assert config.pyext != ""  # .py  This is not valid when pytest runß directly
    # $HOME/Documents/development/displaycal/DisplayCAL
    assert config.PYDIR != ""

    if sys.platform == "linux":
        assert config.XDG_CONFIG_DIR_DEFAULT == "/etc/xdg"
        assert os.path.expanduser("~/.config") == config.XDG_CONFIG_HOME
        assert os.path.expanduser("~/.local/share") == config.XDG_DATA_HOME
        assert os.path.expanduser("~/.local/share") == config.XDG_DATA_HOME_DEFAULT

    # skip the rest of the test for now
    return

    assert [
        "/usr/share/pop",
        os.path.expanduser("~/.local/share/flatpak/exports/share"),
        "/var/lib/flatpak/exports/share",
        "/usr/local/share",
        "/usr/share",
        "/var/lib",
    ] == config.XDG_DATA_DIRS

    from DisplayCAL.meta import VERSION_STRING

    expected_data_dirs = [
        os.path.expanduser("~/.local/share/DisplayCAL"),
        os.path.expanduser("~/.local/share/doc/DisplayCAL"),
        os.path.expanduser(f"~/.local/share/doc/DisplayCAL-{VERSION_STRING}"),
        os.path.expanduser("~/.local/share/doc/displaycal"),
        os.path.expanduser("~/.local/share/doc/packages/DisplayCAL"),
        os.path.expanduser("~/.local/share/flatpak/exports/share/DisplayCAL"),
        os.path.expanduser("~/.local/share/flatpak/exports/share/doc/DisplayCAL"),
        os.path.expanduser(
            f"~/.local/share/flatpak/exports/share/doc/DisplayCAL-{VERSION_STRING}"
        ),
        os.path.expanduser("~/.local/share/flatpak/exports/share/doc/displaycal"),
        os.path.expanduser(
            "~/.local/share/flatpak/exports/share/doc/packages/DisplayCAL"
        ),
        os.path.expanduser("~/.local/share/flatpak/exports/share/icons/hicolor"),
        os.path.expanduser("~/.local/share/icons/hicolor"),
        config.PYDIR,
        os.path.expanduser(
            "~/PycharmProjects/DisplayCAL/venv/lib/python3.9/site-packages/DisplayCAL-3.8.9.3-py3.9-linux-x86_64.egg/DisplayCAL"
        ),
        "/usr/local/share/DisplayCAL",
        "/usr/local/share/doc/DisplayCAL",
        f"/usr/local/share/doc/DisplayCAL-{VERSION_STRING}",
        "/usr/local/share/doc/displaycal",
        "/usr/local/share/doc/packages/DisplayCAL",
        "/usr/local/share/icons/hicolor",
        "/usr/share/DisplayCAL",
        "/usr/share/doc/DisplayCAL",
        f"/usr/share/doc/DisplayCAL-{VERSION_STRING}",
        "/usr/share/doc/displaycal",
        "/usr/share/doc/packages/DisplayCAL",
        "/usr/share/icons/hicolor",
        "/usr/share/pop/DisplayCAL",
        "/usr/share/pop/doc/DisplayCAL",
        f"/usr/share/pop/doc/DisplayCAL-{VERSION_STRING}",
        "/usr/share/pop/doc/displaycal",
        "/usr/share/pop/doc/packages/DisplayCAL",
        "/usr/share/pop/icons/hicolor",
        "/var/lib/DisplayCAL",
        "/var/lib/doc/DisplayCAL",
        f"/var/lib/doc/DisplayCAL-{VERSION_STRING}",
        "/var/lib/doc/displaycal",
        "/var/lib/doc/packages/DisplayCAL",
        "/var/lib/flatpak/exports/share/DisplayCAL",
        "/var/lib/flatpak/exports/share/doc/DisplayCAL",
        f"/var/lib/flatpak/exports/share/doc/DisplayCAL-{VERSION_STRING}",
        "/var/lib/flatpak/exports/share/doc/displaycal",
        "/var/lib/flatpak/exports/share/doc/packages/DisplayCAL",
        "/var/lib/flatpak/exports/share/icons/hicolor",
        "/var/lib/icons/hicolor",
    ]
    assert sorted(config.DATA_DIRS) == sorted(expected_data_dirs)


# get_hidpi_scaling_factor
@pytest.mark.parametrize(
    "platform,expected",
    [
        ("darwin", 1.0),
        ("win32", 1.0),
    ],
)
def test_get_hidpi_scaling_factor_mac_win(monkeypatch, platform, expected):
    monkeypatch.setattr(sys, "platform", platform)
    assert config.get_hidpi_scaling_factor() == expected


def test_get_hidpi_scaling_factor_xrdb(monkeypatch):
    # Simulate Linux, xrdb present, Xft.dpi found
    monkeypatch.setattr(sys, "platform", "linux")
    # Patch which to return True for "xrdb"
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: name == "xrdb")
    # Patch get_default_dpi to return 96
    monkeypatch.setattr(config, "get_default_dpi", lambda: 96)

    # Patch subprocess.Popen to simulate xrdb output
    class DummyPopen:
        def __init__(self, *a, **k):
            pass

        def communicate(self):
            return (b"Xft.dpi:        192\n", b"")

    monkeypatch.setattr("subprocess.Popen", DummyPopen)
    assert config.get_hidpi_scaling_factor() == 2.0


def test_get_hidpi_scaling_factor_xrdb_invalid(monkeypatch):
    # Simulate Linux, xrdb present, Xft.dpi invalid
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: name == "xrdb")
    monkeypatch.setattr(config, "get_default_dpi", lambda: 96)

    class DummyPopen:
        def __init__(self, *a, **k):
            pass

        def communicate(self):
            return (b"Xft.dpi:        notanumber\n", b"")

    monkeypatch.setattr("subprocess.Popen", DummyPopen)
    # Should fall through and return None
    assert config.get_hidpi_scaling_factor() is None


def test_get_hidpi_scaling_factor_kde(monkeypatch):
    # Simulate Linux, no xrdb, KDE desktop, QT_SCREEN_SCALE_FACTORS set
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: False)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setenv("QT_SCREEN_SCALE_FACTORS", "1.5;2.0")

    # Patch wx and real_display_size_mm to avoid wx dependency
    class DummyWx:
        @staticmethod
        def GetApp():
            return None

    monkeypatch.setitem(
        sys.modules, "DisplayCAL.wx_addons", type("mod", (), {"wx": DummyWx})
    )
    # Should use first factor
    assert config.get_hidpi_scaling_factor() == 1.5


def test_get_hidpi_scaling_factor_gnome(monkeypatch):
    # Simulate Linux, no xrdb, not KDE, gsettings present
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: name == "gsettings")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")

    # Patch subprocess.Popen to simulate gsettings output
    class DummyPopen:
        def __init__(self, *a, **k):
            pass

        def communicate(self):
            return (b"uint32 2", b"")

    monkeypatch.setattr("subprocess.Popen", DummyPopen)
    assert config.get_hidpi_scaling_factor() == 2.0


def test_get_hidpi_scaling_factor_none(monkeypatch):
    # Simulate Linux, no xrdb, not KDE, no gsettings
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: False)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    assert config.get_hidpi_scaling_factor() is None


# getcfg debug_print fix (#698)


def test_getcfg_no_debug_print_for_none_default(monkeypatch):
    """debug_print must not fire when the fallback default value is None."""
    monkeypatch.setattr(config, "DEBUG", True)
    mock_debug_print = MagicMock()
    monkeypatch.setattr(config, "debug_print", mock_debug_print)

    fresh_cfg = config.CaseSensitiveConfigParser()
    # "argyll.dir" has DEFAULTS["argyll.dir"] = None
    config.getcfg("argyll.dir", fallback=True, cfg=fresh_cfg)

    mock_debug_print.assert_not_called()


def test_getcfg_debug_print_called_for_non_none_default(monkeypatch):
    """debug_print must fire when the fallback default value is not None."""
    monkeypatch.setattr(config, "DEBUG", True)
    mock_debug_print = MagicMock()
    monkeypatch.setattr(config, "debug_print", mock_debug_print)

    fresh_cfg = config.CaseSensitiveConfigParser()
    # "calibration.ambient_viewcond_adjust" has DEFAULTS value of 0 (not None)
    config.getcfg("calibration.ambient_viewcond_adjust", fallback=True, cfg=fresh_cfg)

    mock_debug_print.assert_called_once()


# getcfg's "*.file" path-correction branch also matched any key ending in
# "profile" (since "profile" itself ends with the substring "file"), so a
# missing/nonexistent path stored under a "...profile" key was silently
# replaced by that key's bundled default instead of being returned as-is --
# breaking every "is this profile path missing?" check built on getcfg.


@pytest.mark.parametrize(
    "name",
    [
        "3dlut.input.profile",
        "3dlut.abstract.profile",
        "3dlut.output.profile",
        "measurement_report.output_profile",
        "measurement_report.devlink_profile",
        "measurement_report.simulation_profile",
        "gamap_profile",
        "tc_precond_profile",
    ],
)
def test_getcfg_does_not_correct_nonexistent_profile_paths(name):
    """A nonexistent path under a "...profile" key must round-trip as-is.

    Regression test: these keys end in "profile", which itself ends with the
    substring "file", so they used to be wrongly caught by the ".file"-only
    path-correction branch meant for keys like "calibration.file" /
    "testchart.file" and silently replaced with the key's bundled default.
    """
    previous = config.getcfg(name, fallback=False)
    try:
        config.setcfg(name, "/no/such/profile.icc")
        assert config.getcfg(name) == "/no/such/profile.icc"
    finally:
        config.setcfg(name, previous)


def test_getcfg_still_corrects_calibration_file():
    """The intended ".file" keys keep falling back when the path is gone."""
    previous = config.getcfg("calibration.file", fallback=False)
    try:
        config.setcfg("calibration.file", "/no/such/calibration.cal")
        assert config.getcfg("calibration.file") != "/no/such/calibration.cal"
    finally:
        config.setcfg("calibration.file", previous)


# initcfg combined "if not module" block (#698)


def _make_ini(tmp_path: os.PathLike) -> None:
    """Write a minimal DisplayCAL.ini so fetch_config_files finds it."""
    ini = tmp_path / "DisplayCAL.ini"
    ini.write_text("[Default]\n")


def test_initcfg_sets_lang_default(monkeypatch, tmp_path):
    """initcfg() without a module sets lang when absent from config."""
    _make_ini(tmp_path)
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_SYS", str(tmp_path))

    fresh_cfg = config.CaseSensitiveConfigParser()
    config.initcfg(cfg=fresh_cfg)

    assert fresh_cfg.get(configparser.DEFAULTSECT, "lang", fallback=None) is not None


def test_initcfg_sets_calibration_ambient_default(monkeypatch, tmp_path):
    """initcfg() without a module sets calibration.ambient_viewcond_adjust when absent."""
    _make_ini(tmp_path)
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_SYS", str(tmp_path))

    fresh_cfg = config.CaseSensitiveConfigParser()
    config.initcfg(cfg=fresh_cfg)

    value = fresh_cfg.get(
        configparser.DEFAULTSECT, "calibration.ambient_viewcond_adjust", fallback=None
    )
    assert value == config.DEFAULTS["calibration.ambient_viewcond_adjust"]


def test_initcfg_sets_profile_save_path_default(monkeypatch, tmp_path):
    """initcfg() without a module sets profile.save_path to STORAGE when absent."""
    _make_ini(tmp_path)
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_SYS", str(tmp_path))

    fresh_cfg = config.CaseSensitiveConfigParser()
    config.initcfg(cfg=fresh_cfg)

    value = fresh_cfg.get(configparser.DEFAULTSECT, "profile.save_path", fallback=None)
    assert value == config.STORAGE


def test_initcfg_module_skips_defaults(monkeypatch, tmp_path):
    """initcfg() with a module arg must not touch the module-only defaults."""
    ini = tmp_path / "DisplayCAL-apply-profiles.ini"
    ini.write_text("[Default]\n")
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))

    fresh_cfg = config.CaseSensitiveConfigParser()
    mock_setcfg = MagicMock()
    monkeypatch.setattr(config, "setcfg", mock_setcfg)

    config.initcfg(module="apply-profiles", cfg=fresh_cfg)

    set_keys = {call.args[0] for call in mock_setcfg.call_args_list}
    assert "lang" not in set_keys
    assert "calibration.ambient_viewcond_adjust" not in set_keys
    assert "profile.save_path" not in set_keys


# writecfg atomicity/locking and oversized-config quarantine (#828)


def test_writecfg_writes_atomically_and_locks(monkeypatch, tmp_path):
    """writecfg() must write via a locked temp file + atomic replace."""
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))

    fresh_cfg = config.CaseSensitiveConfigParser()
    fresh_cfg.add_section(config.configparser.DEFAULTSECT)
    config.setcfg("lang", "en", cfg=fresh_cfg)

    assert config.writecfg(cfg=fresh_cfg) is True

    cfgfile = tmp_path / f"{config.APPBASENAME}.ini"
    assert cfgfile.is_file()
    assert "lang = en" in cfgfile.read_text()

    # No leftover temp files from the atomic-replace step.
    assert [p for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []
    # The lock file used to serialize concurrent writers must exist.
    assert (tmp_path / f"{config.APPBASENAME}.ini.lock").is_file()


def test_writecfg_blocks_while_lock_held(monkeypatch, tmp_path):
    """A concurrent writer must wait for the lock instead of interleaving."""
    import threading
    import time as time_module

    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))
    cfgfile = tmp_path / f"{config.APPBASENAME}.ini"
    lockfilename = tmp_path / f"{config.APPBASENAME}.ini.lock"

    fresh_cfg = config.CaseSensitiveConfigParser()
    fresh_cfg.add_section(config.configparser.DEFAULTSECT)
    config.setcfg("lang", "en", cfg=fresh_cfg)

    # Hold the exclusive lock ourselves first, simulating a second process
    # (e.g. the profile loader) already mid-write.
    held_lockfile = open(lockfilename, "a+b")
    lock = config.FileLock(held_lockfile, exclusive=True, blocking=True)

    result = {}

    def writer():
        result["ok"] = config.writecfg(cfg=fresh_cfg)

    t = threading.Thread(target=writer)
    t.start()
    time_module.sleep(0.2)
    # writecfg() must still be blocked waiting for our lock.
    assert t.is_alive()
    assert not cfgfile.exists()

    lock.unlock()
    held_lockfile.close()
    t.join(timeout=5)

    assert not t.is_alive()
    assert result.get("ok") is True
    assert "lang = en" in cfgfile.read_text()


def test_initcfg_reads_ini_as_utf8(monkeypatch, tmp_path):
    """initcfg() must decode the ini file as UTF-8 regardless of OS locale.

    writecfg() always encodes as UTF-8 (str.encode() defaults to it
    regardless of locale). If initcfg()'s cfg.read() ever again omits an
    explicit encoding, Python falls back to the OS locale's preferred
    encoding, which on Windows without the "Beta: UTF-8" system-locale
    option is a legacy codepage (e.g. cp1252). That mismatch mis-decodes
    non-ASCII option values on every read, and since writecfg() re-encodes
    the already-garbled string as UTF-8 again, the mojibake compounds on
    every read/write cycle (issue #828).
    """
    monkeypatch.setattr(config, "CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(config, "CONFIG_SYS", str(tmp_path))

    value = "C:\\Users\\Foo\\target 110cdm² gamma 2.2.cal"
    ini = tmp_path / "DisplayCAL.ini"
    ini.write_bytes(f"[Default]\nlast_cal_path = {value}\n".encode())

    fresh_cfg = config.CaseSensitiveConfigParser()
    with patch.object(fresh_cfg, "read", wraps=fresh_cfg.read) as mock_read:
        config.initcfg(cfg=fresh_cfg)
        assert mock_read.call_args.kwargs.get("encoding") == "utf-8"

    assert (
        fresh_cfg.get(configparser.DEFAULTSECT, "last_cal_path", fallback=None) == value
    )


def test_fetch_config_files_quarantines_oversized_file(monkeypatch, tmp_path):
    """A pathologically large config file must be quarantined, not parsed."""
    monkeypatch.setattr(config, "MAX_CFG_FILE_SIZE", 64)
    cfgfile = tmp_path / "DisplayCAL.ini"
    cfgfile.write_text("[Default]\nlast_icc_path = " + ("x" * 200) + "\n")

    cfgfiles = config.fetch_config_files(["DisplayCAL"], [str(tmp_path)])

    assert cfgfiles == []
    assert not cfgfile.exists()
    quarantined = list(tmp_path.glob("DisplayCAL.ini.corrupt-*"))
    assert len(quarantined) == 1


def test_fetch_config_files_loads_normal_sized_file(monkeypatch, tmp_path):
    """A normal-sized config file must load as before."""
    monkeypatch.setattr(config, "MAX_CFG_FILE_SIZE", 10 * 1024 * 1024)
    cfgfile = tmp_path / "DisplayCAL.ini"
    cfgfile.write_text("[Default]\nlang = en\n")

    cfgfiles = config.fetch_config_files(["DisplayCAL"], [str(tmp_path)])

    assert cfgfiles == [str(cfgfile)]
    assert cfgfile.exists()


def test_get_ui_toolkit_reads_persisted_preference(monkeypatch):
    """Without an override flag/env var, the persisted ui.toolkit config wins."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL"])
    monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    monkeypatch.setattr(
        config, "getcfg", lambda name: "qt" if name == "ui.toolkit" else None
    )

    assert config.get_ui_toolkit() == "qt"


def test_get_ui_toolkit_defaults_to_wx(monkeypatch):
    """With no flag, env var, or persisted preference, wx is the default."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL"])
    monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    monkeypatch.setattr(
        config, "getcfg", lambda name: "wx" if name == "ui.toolkit" else None
    )

    assert config.get_ui_toolkit() == "wx"


def test_get_ui_toolkit_qt_flag_overrides_persisted_wx(monkeypatch):
    """The --qt flag forces Qt for this process regardless of the saved pref."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL", "--qt"])
    monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    monkeypatch.setattr(
        config, "getcfg", lambda name: "wx" if name == "ui.toolkit" else None
    )

    assert config.get_ui_toolkit() == "qt"


def test_get_ui_toolkit_wx_flag_overrides_persisted_qt(monkeypatch):
    """The --wx flag forces wx for this process regardless of the saved pref."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL", "--wx"])
    monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    monkeypatch.setattr(
        config, "getcfg", lambda name: "qt" if name == "ui.toolkit" else None
    )

    assert config.get_ui_toolkit() == "wx"


def test_get_ui_toolkit_env_var_overrides_persisted_preference(monkeypatch):
    """DISPLAYCAL_UI takes precedence over the persisted ui.toolkit config."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL"])
    monkeypatch.setenv("DISPLAYCAL_UI", "qt")
    monkeypatch.setattr(
        config, "getcfg", lambda name: "wx" if name == "ui.toolkit" else None
    )

    assert config.get_ui_toolkit() == "qt"


def _offer_qt_cfg(monkeypatch, offer_qt=1, toolkit="wx"):
    """Patch getcfg for should_offer_qt_ui() and clear any toolkit override."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL"])
    monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    values = {"ui.offer_qt": offer_qt, "ui.toolkit": toolkit}
    monkeypatch.setattr(config, "getcfg", lambda name: values.get(name))


@pytest.mark.parametrize(
    "argv, env, expected",
    [
        (["DisplayCAL"], None, None),
        (["DisplayCAL", "--qt"], None, "qt"),
        (["DisplayCAL", "--wx"], "qt", "wx"),
        (["DisplayCAL"], "WX", "wx"),
        (["DisplayCAL"], "gtk", None),
    ],
)
def test_get_ui_toolkit_override(monkeypatch, argv, env, expected):
    """Only the --qt/--wx flags and DISPLAYCAL_UI force a toolkit."""
    monkeypatch.setattr(sys, "argv", argv)
    if env is None:
        monkeypatch.delenv("DISPLAYCAL_UI", raising=False)
    else:
        monkeypatch.setenv("DISPLAYCAL_UI", env)

    assert config.get_ui_toolkit_override() == expected


def test_should_offer_qt_ui_on_wx_by_preference(monkeypatch):
    """A wx user who hasn't opted out gets the Qt offer."""
    _offer_qt_cfg(monkeypatch)
    monkeypatch.setattr(config.importlib.util, "find_spec", lambda name: object())

    assert config.should_offer_qt_ui() is True


@pytest.mark.parametrize(
    "offer_qt, toolkit, argv, env",
    [
        (0, "wx", ["DisplayCAL"], None),
        (1, "qt", ["DisplayCAL"], None),
        (1, "wx", ["DisplayCAL", "--wx"], None),
        (1, "wx", ["DisplayCAL"], "wx"),
    ],
    ids=("opted out", "already on Qt", "--wx flag", "DISPLAYCAL_UI=wx"),
)
def test_should_offer_qt_ui_skipped(monkeypatch, offer_qt, toolkit, argv, env):
    """No offer after opting out, on Qt, or when wx is forced for the process."""
    _offer_qt_cfg(monkeypatch, offer_qt, toolkit)
    monkeypatch.setattr(sys, "argv", argv)
    if env:
        monkeypatch.setenv("DISPLAYCAL_UI", env)
    monkeypatch.setattr(config.importlib.util, "find_spec", lambda name: object())

    assert config.should_offer_qt_ui() is False


def test_should_offer_qt_ui_skipped_without_qt(monkeypatch):
    """No offer when PySide6 isn't installed."""
    _offer_qt_cfg(monkeypatch)
    monkeypatch.setattr(
        config.importlib.util,
        "find_spec",
        lambda name: None if name == "PySide6" else object(),
    )

    assert config.should_offer_qt_ui() is False


def test_restart_application_reexecs_process(monkeypatch):
    """restart_application() re-execs via os.execv, stripping --qt/--wx flags."""
    monkeypatch.setattr(sys, "argv", ["DisplayCAL", "--qt", "--verbose"])
    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    monkeypatch.delattr(sys, "frozen", raising=False)
    calls = []
    monkeypatch.setattr(config.os, "execv", lambda *args: calls.append(args))

    config.restart_application()

    assert calls == [
        ("/usr/bin/python3", ["/usr/bin/python3", "DisplayCAL", "--verbose"])
    ]


def test_restart_application_frozen_omits_script_arg(monkeypatch):
    """A frozen (py2exe/PyInstaller) build re-execs its own exe, not a script."""
    monkeypatch.setattr(sys, "argv", ["/Applications/DisplayCAL.app", "--wx"])
    monkeypatch.setattr(sys, "executable", "/Applications/DisplayCAL.app")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    calls = []
    monkeypatch.setattr(config.os, "execv", lambda *args: calls.append(args))

    config.restart_application()

    assert calls == [("/Applications/DisplayCAL.app", ["/Applications/DisplayCAL.app"])]
