from enum import IntEnum
import os
import sys


import pytest
import sys
import builtins

import DisplayCAL.config as config


def test_default_values_1():
    """Test default values of module level variables."""
    from DisplayCAL import config

    config.initcfg()

    assert config.configparser.DEFAULTSECT == "Default"
    assert config.EXE == sys.executable  # venv/bin/python
    assert config.EXEDIR == os.path.dirname(sys.executable)  # venv/bin
    assert config.EXENAME == os.path.basename(sys.executable)  # python
    assert config.ISEXE is False
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.PYFILE != ""
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.PYPATH != ""
    assert config.ISAPP is False  #
    assert config.PYNAME != ""  # _jb_pytest_runner
    # assert config.pyext != ""  # .py  This is not valid when pytest runß directly
    # $HOME/Documents/development/displaycal/DisplayCAL
    assert config.PYDIR != ""

    if sys.platform == "linux":
        assert config.XDG_CONFIG_DIR_DEFAULT == "/etc/xdg"
        assert config.XDG_CONFIG_HOME == os.path.expanduser("~/.config")
        assert config.XDG_DATA_HOME == os.path.expanduser("~/.local/share")
        assert config.XDG_DATA_HOME_DEFAULT == os.path.expanduser("~/.local/share")

    # skip the rest of the test for now
    return

    assert config.XDG_DATA_DIRS == [
        "/usr/share/pop",
        os.path.expanduser("~/.local/share/flatpak/exports/share"),
        "/var/lib/flatpak/exports/share",
        "/usr/local/share",
        "/usr/share",
        "/var/lib",
    ]

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
    "platform,expected", [
        ("darwin", 1.0),
        ("win32", 1.0),
    ]
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
        def __init__(self, *a, **k): pass
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
        def __init__(self, *a, **k): pass
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
    monkeypatch.setitem(sys.modules, "DisplayCAL.wx_addons", type("mod", (), {"wx": DummyWx}))
    # Should use first factor
    assert config.get_hidpi_scaling_factor() == 1.5


def test_get_hidpi_scaling_factor_gnome(monkeypatch):
    # Simulate Linux, no xrdb, not KDE, gsettings present
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("DisplayCAL.util_os.which", lambda name: name == "gsettings")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    # Patch subprocess.Popen to simulate gsettings output
    class DummyPopen:
        def __init__(self, *a, **k): pass
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

