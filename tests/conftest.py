# -*- coding: utf-8 -*-

import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

import DisplayCAL
from DisplayCAL import RealDisplaySizeMM
from DisplayCAL.config import setcfg
from DisplayCAL.argyll import get_argyll_latest_version

import pytest


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
def argyll():
    """Setup ArgyllCMS.

    This will search for ArgyllCMS binaries under ``.local/bin/Argyll*/bin`` and if it
    can not find it, it will download from the source.
    """
    argyll_version = get_argyll_latest_version()
    argyll_download_url = {
        "win32": f"https://www.argyllcms.com/Argyll_V{argyll_version}_win64_exe.zip",
        "darwin": f"https://www.argyllcms.com/Argyll_V{argyll_version}_osx10.6_x86_64_bin.tgz",
        "linux": f"https://www.argyllcms.com/Argyll_V{argyll_version}_linux_x86_64_bin.tgz",
    }

    # first look in to ~/local/bin/ArgyllCMS
    home = pathlib.Path().home()
    argyll_search_paths = [
        home / ".local" / "bin" / "Argyll" / "bin",
        home / ".local" / "bin" / f"Argyll_V{argyll_version}" / "bin",
    ]

    argyll_path = None
    for path in argyll_search_paths:
        if path.is_dir():
            argyll_path = path
            setcfg("argyll.dir", str(argyll_path.absolute()))
            break

    if argyll_path:
        yield argyll_path
        return

    # apparently argyll has not been found
    # download from source
    url = argyll_download_url[sys.platform]

    argyll_temp_path = tempfile.mkdtemp()
    # store current working directory
    current_working_directory = os.getcwd()

    # change dir to argyll temp path
    os.chdir(argyll_temp_path)

    tar_file_name = "Argyll.tgz"
    if not os.path.exists(tar_file_name):
        print(f"Downloading: {tar_file_name}")
        # Download the tar file if it doesn't already exist
        subprocess.call(["/usr/bin/curl", url, "-o", tar_file_name])
    else:
        print(f"Tar file already exists: {tar_file_name}")
        print("Not downloading it again!")

    print(f"Decompressing Tarfile: {tar_file_name}")
    with tarfile.open(tar_file_name) as tar:
        tar.extractall()

    def cleanup():
        # cleanup the test
        shutil.rmtree(argyll_temp_path)
        os.chdir(current_working_directory)

    argyll_path = pathlib.Path(argyll_temp_path) / f"Argyll_V{argyll_version}" / "bin"
    print(f"argyll_path: {argyll_path}")
    if argyll_path.is_dir():
        setcfg("argyll.dir", str(argyll_path.absolute()))
        yield argyll_path
        cleanup()
    else:
        cleanup()
        pytest.skip("ArgyllCMS can not be setup!")


@pytest.fixture(scope="function")
def random_icc_profile():
    """Create a random ICCProfile suitable for modification."""
    import tempfile
    from DisplayCAL import colormath
    from DisplayCAL import ICCProfile

    rec709_gamma18 = list(colormath.get_rgb_space("Rec. 709"))
    icc_profile = ICCProfile.ICCProfile.from_rgb_space(
        rec709_gamma18, b"Rec. 709 gamma 1.8"
    )
    icc_profile_path = tempfile.mktemp(suffix=".icc")
    icc_profile.write(icc_profile_path)

    yield icc_profile, icc_profile_path

    # clean the file
    os.remove(icc_profile_path)


@pytest.fixture(scope="function")
def patch_subprocess(monkeypatch):
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
