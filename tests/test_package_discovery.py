"""Regression tests for the package discovery config in pyproject.toml.

See issue #993: namespace package discovery only had an exclude list, so any
other top-level directory became a package. Debian builds once per supported
Python and the second build picked up the first one's install tree under
`debian/`, which dh_python3 rejects.
"""

import tomllib
from pathlib import Path

from setuptools import find_namespace_packages

ROOT = Path(__file__).resolve().parent.parent


def _find_config():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["setuptools"]["packages"]["find"]


def test_only_displaycal_packages_are_discovered(tmp_path):
    """Stray top-level dirs with .py files must not be picked up as packages."""
    config = _find_config()
    (tmp_path / "DisplayCAL" / "sub").mkdir(parents=True)
    (tmp_path / "DisplayCAL" / "__init__.py").touch()
    (tmp_path / "DisplayCAL" / "sub" / "mod.py").touch()
    stray = tmp_path / "debian" / "displaycal" / "usr" / "lib" / "DisplayCAL"
    stray.mkdir(parents=True)
    (stray / "__init__.py").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "conf.py").touch()

    packages = find_namespace_packages(
        str(tmp_path),
        include=config.get("include", ("*",)),
        exclude=config.get("exclude", ()),
    )

    assert sorted(packages) == ["DisplayCAL", "DisplayCAL.sub"]


def test_real_tree_discovers_only_displaycal_packages():
    """The repo checkout itself must only yield DisplayCAL packages."""
    config = _find_config()

    packages = find_namespace_packages(
        str(ROOT),
        include=config.get("include", ("*",)),
        exclude=config.get("exclude", ()),
    )

    assert "DisplayCAL" in packages
    assert all(p == "DisplayCAL" or p.startswith("DisplayCAL.") for p in packages)
