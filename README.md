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
DisplayCAL users, to contribute back to this great tool.

This project is based on the ``HEAD`` of the Sourceforge version, which has 5 extra
commits that Florian has created after the ``3.8.9.3`` release on 14 Jan 2020.

Status Update (30 April 2022)
-----------------------------

DisplayCAL is in PyPI now (yay!).

Here is a screenshots showing the tool working with Python 3.9:

![image](https://user-images.githubusercontent.com/1786804/161440351-9d25ce84-d51b-4efc-90b8-7d8b2d031ad6.png)

Currently, DisplayCAL is working with Python 3.9.7 + wxPython 4.1.1.

Here is a list of things that is working:

- The UI and general functionality.
- Calibration + Characterization (Profiling).
- Installing the created ICC profile.
- Installing the created ICC profiles as root.
- Profile info window is now fully working (on some systems we still have an issue
  related to default values #67).
- Measurement report creation.
- Creating, displaying and uploading Colorimeter Corrections.
- Measuring and reporting display uniformity.
- Creating charts with Test Chart Editor and creating diagnostic 3d data.
- Creating 3D LUTs.
- and a lot of other stuff is working properly.

What is not working (yet)
-------------------------

- There are tons of ``bytes/str`` related issues, getting fixed very quickly but more
  tests are needed.
- Please create [issues](https://github.com/eoyilmaz/displaycal-py3/issues)

How to install
--------------

Currently, there is no ``RPM``, ``DEB``, ``APP`` or ``MSI`` packages. 
To test the code you can either run it directly from the source or install it as a ``sdist`` package.  To do this: 

Prequisties:
* Assorted C/C++ builder tools
* dbus-1
* glib 2.0
* gtkd 3
* libxxf86vm
* pkg-config

Please install these from your package manager. 

```shell
# Brew on Macs
brew install pkg-config dbus glib gtk+3

# Debian installs
apt-get install build-essential dbus libglib2.0-dev pkg-config libgtk-3-dev libxxf86vm-dev
```

Then pull the source and create a virtual environment:

```shell
git clone https://github.com/eoyilmaz/displaycal-py3
python -m venv ./displaycal_venv
source ./displaycal_venv/bin/activate  # Windows: .\displaycal_venv\Scripts\activate.bat
cd ./displaycal-py3/
pip install -r requirements.txt
python -m build
pip install dist/DisplayCAL-3.9.0-*.whl
```

This should install DisplayCAL. To run the UI:

```shell
displaycal
```

ATTENTION!
----------

Previously the ``--install-data=$HOME/.local`` option has to be used with the
``setup.py`` script in order to let the DisplayCAL to find the required data files. But
it is not needed anymore, and it is a good idea to delete the ``DisplayCAL*`` files and
folders from the ``site-packages`` folder of your ``python`` interpreter if you used
that option in a previous version of ``DisplayCAL-py3``.

Road Map
--------

Some ideas on where to focus on future development:

- ~~Add DisplayCAL to PyPI 
  ([#83](https://github.com/eoyilmaz/displaycal-py3/issues/83)).~~
- Try to move the UI to Qt. This is a big ticket. The motivation behind that is that I'm
  much more experienced with Qt. In fact, I have zero experience with ``wxPython``.
- Make the code fully compliant with PEP8 with the modification of hard wrapping the
  code at 88 characters instead of 80 characters. This also means a lot of class and
  method/function names will be changed.
- Create unit tests with ``Pytest`` and reach to 100% code coverage. The ``3.8.9.3``
  version of DisplayCAL is around 120k lines of Python code (other languages are not
  included) and there are no tests (or the repository I adapted doesn't contain any
  tests). This is a nightmare and super hard to maintain. This is an ongoing work, with
  the latest commits we have over 150 tests (which is super low for, should be 
  thousands) and the code coverage is around 25% (again this is super low, should be
  over 99%).
- Maybe I'm not experienced enough, and I'm wrong on saying this, but I don't see the
  motivation behind having a C-Extension for ``EDID``, ``XRandr`` etc. stuff. It should
  be possible to cover all the functionality of this extension and stay purely in
  Python. It is super hard to debug (for me at least) and super hard to maintain (again,
  for me).
- Replace the ``wexpect.py`` with the latest release of ``Pexpect``. I'm not very
  familiar with this module, and there is no comment in the code on why we have
  a ``wexpect.py`` instead of using the PyPI version of ``Pexpect``.
- Replace ``os.path`` related stuff with ``pathlib``.
- Organize the module structure, move UI related stuff in to ``ui`` module etc., move
  non-source files into their own folders.
- Update the ``Remaining time`` calculation during profiling to estimate the time by
  also considering the luminance of the remaining patches to have a better estimation.
  Because, patches with higher luminance values are measured quickly than patches with
  lower luminance values.
- ~~Replace the ``DisplayCAL.ordereddict.OrderedDict`` with the pure Python ``dict``
  which is ordered after Python 3.6.~~ (Done!)

Issues related to these ideas have been created. If you have a feature request, you can
create more issues or share your comment on the already created issues or create merge
requests that are fixing little or big things.

Because there are very little automated tests, **I need the code to be tested
constantly**. Please help me with that.

Have fun!
