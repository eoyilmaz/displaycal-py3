![license](https://img.shields.io/badge/License-GPL%20v3-blue.svg)
![pyversion](https://img.shields.io/pypi/pyversions/DisplayCAL.svg)
![pypiversion](https://img.shields.io/pypi/v/DisplayCAL.svg)
![wheel](https://img.shields.io/pypi/wheel/DisplayCAL.svg)

DisplayCAL Python 3 Project
===========================

This project intended to modernize the DisplayCAL code including Python 3 support.

Florian Höch, the original developer, did an incredible job of creating and maintaining
DisplayCAL for all these years. But, it seems that, during the pandemic, very
understandably, he lost his passion to the project. Now, it is time for us, the
DisplayCAL community, to contribute back to this great tool.

This project is based on the ``HEAD`` of the Sourceforge version, which had 5 extra
commits that Florian has created after the ``3.8.9.3`` release on 14 Jan 2020.

Status Update (18 May 2022)
---------------------------

DisplayCAL is in [PyPI](https://pypi.org/project/DisplayCAL/) now (yay!).

Here is a screenshots showing the tool working with Python 3.10:

![image](https://user-images.githubusercontent.com/1786804/169152229-e06ff549-55fe-4149-8742-405446e6b01f.png)

Currently, DisplayCAL is working with Python 3.8, 3.9, 3.10 and 3.11 and wxPython 4.1.1 to 4.2.1.

Here is a list of things that is working:

- The UI and general functionality.
- Calibration + Characterization (Profiling).
- Installing the created ICC profile both locally and system-wide (requires root
  permissions).
- Profile Info window is now fully working (on some systems we still have an issue
  related to default values [#67](https://github.com/eoyilmaz/displaycal-py3/issues/67)).
- Measurement report creation.
- Creating, displaying and uploading Colorimeter Corrections.
- Measuring and reporting display uniformity.
- Creating charts with Test Chart Editor and creating diagnostic 3d data.
- Creating 3D LUTs.
- Creating synthetic ICC profiles.
- and a lot of other stuff are working properly.

What is not working
-------------------

- Everything should be working now. But, incase you encounter any bugs please create
  [issues](https://github.com/eoyilmaz/displaycal-py3/issues).

How to install
--------------

Currently, there is no ``RPM``, ``DEB``, ``APP`` or ``MSI`` packages. These are coming
soon.

To test the code you can either run it directly from the source or install it as a
``sdist`` package.  To do this: 

Prerequisites:

* Assorted C/C++ builder tools
* dbus
* glib 2.0 or glibc
* gtk-3
* libXxf86vm
* pkg-config

Please install these from your package manager. 

```shell
# Brew on MacOS
brew install glib gtk+3 python@3.10

# Debian installs
apt-get install build-essential dbus libglib2.0-dev pkg-config libgtk-3-dev libxxf86vm-dev

# Fedora core installs
dnf install gcc glibc-devel dbus pkgconf gtk3-devel libXxf86vm-devel
```

Then pull the source:

```shell
git clone https://github.com/eoyilmaz/displaycal-py3
cd ./displaycal-py3/
```

At this stage you may want to switch to the ``develop`` branch to test some new features
or possibly fixed issues over the ``main`` branch.

```shell
git checkout develop
```

Then you can build and install DisplayCAL using:

```shell
make build
make install
```

If this errors out for you, you can follow the [Manual Setup](https://github.com/eoyilmaz/displaycal-py3#manually-setup)
section below.

Otherwise, this should install DisplayCAL. To run the UI:

```shell
make launch
```

Manually Setup
--------------

If the `makefile` workflow doesn't work for you, you can setup the virtual environment
manually:

```shell
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m build
pip install dist/DisplayCAL-3.9.*.whl
```

This should install DisplayCAL. To run the UI:

```shell
displaycal
```

Road Map
--------

Here are some ideas on where to focus the future development effort:

- ~~Add DisplayCAL to PyPI 
  ([#83](https://github.com/eoyilmaz/displaycal-py3/issues/83)).~~ (Done!
  [Display PyPI Page](https://pypi.org/project/DisplayCAL/))
- ~~Replace the ``DisplayCAL.ordereddict.OrderedDict`` with the pure Python ``dict``
  which is ordered after Python 3.6.~~ (Done!)
- ~~Make the code fully compliant with PEP8 with the modification of hard wrapping the
  code at 88 characters instead of 80 characters. This also means a lot of class and
  method/function names will be changed.~~ Thanks to ``black`` and some ``flake8`` this
  is mostly done.
- Remove the ``RealDisplaySizeMM`` C-Extension which is just for creating a 100 x 100 mm
  dialog and getting ``EDID`` information. It should be possible to cover all the same
  functionality of this extension and stay purely in Python. It is super hard to debug
  and super hard to maintain.
- Try to move the UI to Qt. This is a big ticket. The motivation behind this is that it
  is a better library and more developer understands it and the current DisplayCAL
  developers have more experience with it.
- Create unit tests with ``Pytest`` and reach to ~100% code coverage. The ``3.8.9.3``
  version of DisplayCAL is around 120k lines of Python code (other languages are not
  included) and there are no tests (or the repository this project has adapted didn't
  contain any tests). This is a nightmare and super hard to maintain. This is an ongoing
  work, with the latest commits we have around 200 tests (which is super low, should be
  thousands) and the code coverage is around 26% (again this is super low, should be
  over 99%).
- Replace the ``wexpect.py`` with the latest release of ``Pexpect``. There is no comment
  in the code on why we have a ``wexpect.py`` instead of using the PyPI version of
  ``Pexpect``. Update: we believe it is because ``Pexpect`` doesn't support Windows.
  Then it is a good idea to port the DisplayCAL implementation to the ``Pexpect``
  project.
- Replace ``os.path`` related code with ``pathlib.Path`` class.
- Organize the module structure, move UI related stuff in to ``ui`` module etc., move
  data files into their own folders.
- Use [importlib_resources](https://importlib-resources.readthedocs.io/en/latest/using.html)
  module for reading data files.
- Update the ``Remaining time`` calculation during profiling to estimate the time by
  also considering the luminance of the remaining patches to have a better estimation.
  Because, patches with higher luminance values are measured quickly than patches with
  lower luminance values.

Issues related to these ideas have been created. If you have a feature request, you can
create more issues or share your comment on the already created issues or create merge
requests that are fixing little or big things.

Because there are very little automated tests, **the code need to be tested 
constantly**. Please help us with that.

Have fun!
