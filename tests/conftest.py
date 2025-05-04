# -*- coding: utf-8 -*-

import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from requests import HTTPError

import pytest

from DisplayCAL import config
from DisplayCAL.util_os import which
from DisplayCAL.worker import Worker

import DisplayCAL
from DisplayCAL import RealDisplaySizeMM
from DisplayCAL.argyll import (
    get_argyll_latest_version,
    get_argyll_version_string,
    parse_argyll_version_string,
)
from DisplayCAL.colormath import get_rgb_space
from DisplayCAL.config import setcfg, writecfg
from DisplayCAL.icc_profile import ICCProfile


@pytest.fixture(scope="module")
def data_files():
    """Generate data file list."""
    #  test/data
    extensions = ["*.txt", "*.tsv", "*.lin", "*.cal", "*.ti1", "*.ti3", "*.icc"]

    displaycal_parent_dir = pathlib.Path(DisplayCAL.__file__).parent
    search_paths = [
        displaycal_parent_dir,
        displaycal_parent_dir / "presets",
        displaycal_parent_dir / "ti1",
        displaycal_parent_dir.parent / "misc" / "ti3",
        displaycal_parent_dir.parent / "tests" / "data",
        displaycal_parent_dir.parent / "tests" / "data" / "sample",
        displaycal_parent_dir.parent / "tests" / "data" / "sample" / "issue129",
        displaycal_parent_dir.parent / "tests" / "data" / "sample" / "issue268",
        displaycal_parent_dir.parent / "tests" / "data" / "icc",
    ]
    d_files = {}
    for path in search_paths:
        for extension in extensions:
            # add files from DisplayCal/presets folder
            for element in path.glob(extension):
                d_files[element.name] = element

    yield d_files


@pytest.fixture(scope="module")
def data_path():
    """Return the tests/data folder path."""
    displaycal_parent_dir = pathlib.Path(DisplayCAL.__file__).parent
    return displaycal_parent_dir.parent / "tests" / "data"


@pytest.fixture(scope="module")
def setup_argyll():
    """Setup ArgyllCMS.

    This will search for ArgyllCMS binaries under ``.local/bin/Argyll*/bin`` and if it
    can not find it, it will download from the source.
    """
    # check if ArgyllCMS is already installed
    xicclu_path = which("xicclu")
    if xicclu_path:
        # ArgyllCMS is already installed
        argyll_path = pathlib.Path(xicclu_path).parent
        setcfg("argyll.dir", str(argyll_path.absolute()))
        argyll_version_string = get_argyll_version_string("xicclu", True, [str(argyll_path)])
        argyll_version = parse_argyll_version_string(argyll_version_string)
        print(f"argyll_version_string: {argyll_version_string}")
        print(f"argyll_version: {argyll_version}")
        setcfg("argyll.version", argyll_version_string)
        writecfg()
        yield argyll_path
        return

    # first look in to ~/local/bin/ArgyllCMS
    home = pathlib.Path().home()
    argyll_search_paths = glob.glob(str(home / ".local" / "bin" / "Argyll*" / "bin"))

    argyll_path = None
    for path in reversed(argyll_search_paths):
        path = pathlib.Path(path)
        if path.is_dir():
            argyll_path = path
            setcfg("argyll.dir", str(argyll_path.absolute()))
            argyll_version_string = get_argyll_version_string(
                "xicclu", True, [str(path)]
            )
            argyll_version = parse_argyll_version_string(argyll_version_string)
            print(f"argyll_version_string: {argyll_version_string}")
            print(f"argyll_version: {argyll_version}")
            setcfg("argyll.version", argyll_version_string)
            writecfg()
            break

    print(f"argyll_path: {argyll_path}")
    if argyll_path:
        yield argyll_path
        return

    # apparently argyll has not been found
    # download from source
    get_argyll_latest_version.cache_clear()
    argyll_version = get_argyll_latest_version()
    argyll_domain = config.defaults.get("argyll.domain", "")
    argyll_download_url = {
        "win32": f"{argyll_domain}/Argyll_V{argyll_version}_win64_exe.zip",
        "darwin": f"{argyll_domain}/Argyll_V{argyll_version}_osx10.6_x86_64_bin.tgz",
        "linux": f"{argyll_domain}/Argyll_V{argyll_version}_linux_x86_64_bin.tgz",
    }

    url = argyll_download_url[sys.platform]

    argyll_temp_path = tempfile.mkdtemp()
    # store current working directory
    current_working_directory = os.getcwd()

    # change dir to argyll temp path
    os.chdir(argyll_temp_path)

    # Download the package file if it doesn't already exist
    argyll_package_file_name = "Argyll.tgz" if sys.platform != "win32" else "Argyll.zip"
    if not os.path.exists(argyll_package_file_name):
        print(f"Downloading: {argyll_package_file_name}")
        print(f"URL: {url}")
        worker = Worker()
        result = worker.download(url, download_dir=argyll_temp_path)
        if isinstance(result, HTTPError):
            print(f"Error downloading {url}: {result}")
            raise result
        download_path = result
        print(f"Downloaded to: {download_path}")
        if os.path.exists(download_path):
            shutil.move(download_path, argyll_package_file_name)
    else:
        print(f"Package file already exists: {argyll_package_file_name}")
        print("Not downloading it again!")

    print(f"Decompressing Argyll Package: {argyll_package_file_name}")
    if sys.platform == "win32":
        with zipfile.ZipFile(argyll_package_file_name, "r") as zip_ref:
            zip_ref.extractall()
    else:
        with tarfile.open(argyll_package_file_name) as tar:
            tar.extractall()

    def cleanup():
        # cleanup the test
        shutil.rmtree(argyll_temp_path, ignore_errors=True)
        os.chdir(current_working_directory)

    argyll_path = pathlib.Path(argyll_temp_path) / f"Argyll_V{argyll_version}" / "bin"
    print(f"argyll_path: {argyll_path}")
    if argyll_path.is_dir():
        print("argyll_path is valid!")
        setcfg("argyll.dir", str(argyll_path.absolute()))
        argyll_version_string = get_argyll_version_string("xicclu", True, [str(argyll_path)])
        argyll_version = parse_argyll_version_string(argyll_version_string)
        print(f"argyll_version_string: {argyll_version_string}")
        print(f"argyll_version: {argyll_version}")
        setcfg("argyll.version", argyll_version_string)
        writecfg()
        os.environ["PATH"] = f"{argyll_path}{os.pathsep}{os.environ['PATH']}"
        yield argyll_path
        cleanup()
    else:
        print("argyll_path is invalid!")
        cleanup()
        pytest.skip("ArgyllCMS can not be setup!")


@pytest.fixture(scope="function")
def random_icc_profile():
    """Create a random ICCProfile suitable for modification."""
    rec709_gamma18 = list(get_rgb_space("Rec. 709"))
    icc_profile = ICCProfile.from_rgb_space(
        rec709_gamma18, b"Rec. 709 gamma 1.8"
    )
    icc_profile_path = tempfile.mktemp(suffix=".icc")
    icc_profile.write(icc_profile_path)

    yield icc_profile, icc_profile_path

    # clean the file
    os.remove(icc_profile_path)


@pytest.fixture(scope="function")
def patch_subprocess():
    """Patch subprocess.

    Yields:
        Any: The patched subprocess class.
    """

    class Process:
        def __init__(self, output=None):
            self.output = output

        def communicate(self):
            return self.output, None

    class PatchedSubprocess:
        passed_args = []
        passed_kwargs = {}
        STDOUT = None
        PIPE = None
        output = {}
        wShowWindow = None
        STARTUPINFO = subprocess.STARTUPINFO if sys.platform == "win32" else None
        STARTF_USESHOWWINDOW = (
            subprocess.STARTF_USESHOWWINDOW if sys.platform == "win32" else None
        )
        SW_HIDE = subprocess.SW_HIDE if sys.platform == "win32" else None

        @classmethod
        def Popen(cls, *args, **kwargs):
            cls.passed_args += args
            cls.passed_kwargs.update(kwargs)
            process = Process(output=cls.output.get("".join(*args)))
            return process

    yield PatchedSubprocess


@pytest.fixture(scope="function")
def patch_argyll_util(monkeypatch):
    """Patch argyll.

    Yields:
        Any: The patched argyll class.
    """

    class PatchedArgyll:
        passed_util_name = []

        @classmethod
        def get_argyll_util(cls, util_name):
            cls.passed_util_name.append(util_name)
            return "dispwin"

    monkeypatch.setattr("DisplayCAL.RealDisplaySizeMM.argyll", PatchedArgyll)

    yield PatchedArgyll


@pytest.fixture(scope="function")
def clear_displays():
    """Clear RealDisplaySizeMM._displays."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
