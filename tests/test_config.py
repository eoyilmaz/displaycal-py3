# -*- coding: utf-8 -*-

import os
import sys


def test_default_values_1():
    """Test default values of module level variables."""
    from DisplayCAL import config
    config.initcfg()

    assert config.configparser.DEFAULTSECT == "Default"
    assert config.exe == sys.executable  # venv/bin/python
    assert config.exedir == os.path.dirname(sys.executable)  # venv/bin
    assert config.exename == os.path.basename(sys.executable)  # python
    assert config.isexe is False
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.pyfile != ""
    # $HOME/.local/bin/pycharm-{PYCHARMVERSION}/plugins/python/helpers/pycharm/_jb_pytest_runner.py
    assert config.pypath != ""
    assert config.isapp is False  #
    assert config.pyname != ""  # _jb_pytest_runner
    assert config.pyext != ""  # .py
    # $HOME/Documents/development/displaycal/DisplayCAL
    assert config.pydir != ""

    if sys.platform == "linux":
        assert config.xdg_config_dir_default == "/etc/xdg"
        assert config.xdg_config_home == os.path.expanduser("~/.config")
        assert config.xdg_data_home == os.path.expanduser("~/.local/share")
        assert config.xdg_data_home_default == os.path.expanduser("~/.local/share")

    # skip the rest of the test for now
    return

    assert config.xdg_data_dirs == [
        "/usr/share/pop",
        os.path.expanduser("~/.local/share/flatpak/exports/share"),
        "/var/lib/flatpak/exports/share",
        "/usr/local/share",
        "/usr/share",
        "/var/lib",
    ]

    from DisplayCAL.__version__ import VERSION_STRING

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
        config.pydir,
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
    assert sorted(config.data_dirs) == sorted(expected_data_dirs)
