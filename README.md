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
commits that Florian has created over the ``3.8.9.3`` release on 14 Jan 2020.

Thanks to all the efforts put by the community DisplayCAL is now working with Python
3.8+:

![image](screenshots/DisplayCAL-screenshot-GNOME-3.9.5-running_on_python3.10.png)

Installation Instructions
=========================

Follow the instructions depending on you OS:

- Windows:
  - [Install with Installer](#install-with-installer-windows)
  - [Install through PyPI](#install-through-pypi-windows)
  - [Build from source](#build-from-source-windows)
  - [Build the Installer](#build-the-installer-windows)
- Linux and MacOS:
  - [Prerequisites](#prerequisites-linux-and-macos)
  - [Instal through PyPI](#install-through-pypi-linux--macos)
  - [Build From Source (Makefile Workflow)](#build-from-source-makefile-workflow-linux--macos)
  - [Build From Source (Manual)](#build-from-source-manual-linux--macos)

Installation Instructions (Windows)
===================================

Install with Installer (Windows)
--------------------------------

We now have a proper [installer](https://www.github.com/eoyilmaz/displaycal-py3/releases) for Windows
and this is the preffered way of running DisplayCAL under Windows (unless you want to
test the latest code).

Install through PyPI (Windows)
------------------------------

If you desire so, you can install DisplayCAL through PyPI. You need to use Python 3.9,
3.10 or 3.11 and use the system Python, so no Virtual Environments. We recommend using
Python 3.11. Here is the installation procedure:

1- Download and install one of Python 3.9, 3.10 or 3.11. Unfortunatelly Python 3.12 is
   not currently working:

   Here is some download links that are now hidden in Python's home page:
   - [python-3.9.13-amd64.exe](https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe)
   - [python-3.10.11-amd64.exe](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe)
   - Python 3.11 can be downloaded directly from [Python.org](https://www.python.org/downloads/windows/).
   - Python 3.12 is not supported currently.

   Some of the libraries that DisplayCAL depends on are not working or not supported
   with Python 3.12. So, stick with Python 3.9, 3.10 or 3.11 until we find a solution.

   Also don't forget to select "Add Python 3.xx to PATH" in the installer.

   ![image](screenshots/Python_3.9_Installation_Windows.jpg)

2- Download and install Visual Studio Build Tools:

   Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/

   Select "Desktop development with C++" only:

   ![image](screenshots/Visual_Studio_Build_Tools.jpg)

3- Install DisplayCAL through PyPI:

   After both Python and Visual Studio Build Tools are installed run the following in
   the command prompt:

   ```shell
   pip install displaycal
   ```

4- Run DisplayCAL:

   ```shell
   python -m DisplayCAL
   ```

> [!WARNING]
> Under Windows use the system Python installation instead of a virtual environment as
> Wexpect module cannot read ArgyllCMS command outputs from inside a virtual
> environment.

> [!WARNING]
> Under Windows don't run DisplayCAL inside the IDE (Vscode, Pycharm etc.) terminal as
> most of the IDE's are creating virtual terminals and it is not possible to capture the
> command outputs with Wexpect.

Build From Source (Windows)
---------------------------

Under Windows the `makefile` workflow will not work, using a virtual environment is also
breaking Wexpect module, so you need to use your system Python installation. Currently,
DisplayCAL will run with Python 3.9, 3.10 and 3.11, but Python 3.12 is not supported. To
build DisplayCAL from source under Windows follow these steps:

1- Download and install one of Python 3.9, 3.10 or 3.11. Unfortunatelly Python 3.12 is
   not currently working:

   Here is some download links that are now hidden in Python's home page:
   - [python-3.9.13-amd64.exe](https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe)
   - [python-3.10.11-amd64.exe](https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe)
   - Python 3.11 can be downloaded directly from [Python.org](https://www.python.org/downloads/windows/).
   - Python 3.12 is not supported currently.

   Some of the libraries that DisplayCAL depends on are not working or supported with
   Python 3.12. So, stick with Python 3.9, 3.10 or 3.11 until we find a solution.

   Also don't forget to select "Add Python 3.xx to PATH" in the installer.

   ![image](screenshots/Python_3.9_Installation_Windows.jpg)

2- Download and install Visual Studio Build Tools:

   Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/

   Select "Desktop development with C++" only:

   ![image](screenshots/Visual_Studio_Build_Tools.jpg)

3- Download and install Git:

   https://www.git-scm.com/download/win

   When installer asks, the default settings are okay.

4- Clone DisplayCAL repository, build and install it:

   Open up a command prompt and run the following:

   ```shell
   cd %HOME%
   git clone https://github.com/eoyilmaz/displaycal-py3.git
   cd displaycal-py3
   ```

   Then we suggest switching to the `develop` branch as we would have fixes introduced
   to that branch the earliest. To do that run:

   ```shell
   git checkout develop
   ```

  > [!TIP]
  > If you want to switch to some other branches to test the code you can replace
  > `develop` in the previous command with the branch name:
  > ```shell
  > git checkout 367-compiled-sucessfully-in-w10-py311-but-createprocess-fails-call-to-dispread-to-measure
  > ```

   Let's install the requirements, build displaycal and install it:

   ```shell
   pip install -r requirements.txt -r requirements-dev.txt
   python -m build
   pip install dist/DisplayCAL-3.9.*.whl
   ```

5- Run DisplayCAL:

   ```shell
   python -m DisplayCAL
   ```

6- To rebuild and install it again:

   First remove the old installation:

   ```shell
   pip uninstall displaycal
   ```

   Build and install it again:

   ```shell
   python -m build
   pip install dist/DisplayCAL-3.9.*.whl
   ```

Build The Installer (Windows)
-----------------------------

To build the installer for your own use you can follow these steps:

1- Follow the instructions explained in
   [Build From Source (Windows)](#build-from-source-windows) to build DisplayCAL from
   its source.

2- Use the `DisplayCAL\freeze.py` script to generate the frozen executables. Under the
   `displaycal-py3` folder run the following:

   ```shell
   python DisplayCAL\freeze.py
   ```

   This should generate a folder under the `dist` folder with a name similar to
   `py2exe.win32-py3.11-DisplayCAL-3.9.12`.

   All the executables and resources to run DisplayCAL are placed under this folder. So,
   you can directly run the executables under this folder.

3- Download and install [Inno Setup](https://jrsoftware.org/isdl.php#stable):

4- Generate the Inno Setup script:

   ```shell
   python setup.py inno
   ```

   This will generate a file called `py2exe.win32-py3.11-Setup-inno.iss`

5- Run Inno Setup to build the script:

   ```shell
   cd dist
   "C:\Program Files (x86)\Inno Setup 6\iscc" py2exe.win32-py3.11-Setup-inno.iss
   ```

6- This should now generate the installer with the name
   `DisplayCAL-3.9.12-Setup.exe` that you can use to install DisplayCAL to
   any Windows computer.

Installation Instructions (Linux and MacOS)
===========================================

Prerequisites (Linux and MacOS)
-------------------------------

Currently, the only way of installing DisplayCAL on Linux and MacOS is to install it
through **PyPI** or to build it from source. Proper installers are coming soon!

To install DisplayCAL there are some prerequisites:

* Assorted C/C++ builder tools
* dbus
* glib 2.0 or glibc
* gtk-3
* libXxf86vm
* pkg-config
* python3-devel

Please install these from your package manager. 

```shell
# Brew on MacOS
brew install glib gtk+3 python@3.11

# Debian installs
apt-get install build-essential dbus libglib2.0-dev pkg-config libgtk-3-dev libxxf86vm-dev python3-dev

# Fedora core installs
dnf install gcc glibc-devel dbus pkgconf gtk3-devel libXxf86vm-devel python3-devel
```

> [!NOTE]
> Note, if your system's default python is outside the supported range you will need to
> install a supported version and its related devel package.

Install through PyPI (Linux & MacOS)
------------------------------------

Installing through PyPI is straight forward. We highly suggest using a virtual
environment and not installing it to the system python:

Be sure that you are using the correct Python version:

```shell
python --version
```

Outputs:

```shell
Python 3.11.9
```

Currently Python 3.12+ is not supported.

Create a virtual environment:

```shell
python -m venv venv-displaycal
source venv-diplaycal/bin/activate
pip install displaycal
```

and now you can basically run `displaycal`:

```shell
displaycal
```

If you close the current terminal and run a new one, you need to activate the virtual
environment before calling `displaycal`:

```shell
source venv-diplaycal/bin/activate
displaycal
```

Build From Source (Makefile Workflow) (Linux & MacOS)
-----------------------------------------------------

To test the latest code you can build DisplayCAL from its source. To do that:

Pull the source:

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

The build step assumes your system has a `python3` binary available that is
within the correct range. If your system `python3` is not supported and you
installed a new one, you can try passing it to the build command:

```shell
$ python3 --version
# Python 3.12.2
$ make build # this will fail
$ python3.11 --version
# Python 3.11.8
$ make SYSTEM_PYTHON=python3.11 build # should work
```

If this errors out for you, you can follow the
[Build From Source (Linux & MacOS)](#build-from-source-linux--macos) section below.

Otherwise, this should install DisplayCAL. To run the UI:

```shell
make launch
```

Build From Source (Manual) (Linux & MacOS)
------------------------------------------

If the `makefile` workflow doesn't work for you, you can setup the virtual environment
manually. Ensure the python binary you're using is supported:

```shell
python -m venv .venv # python3.11 -m venv .venv if system python is not a supported version
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
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
- Replace the ``wexpect.py`` with the latest release of ``Wexpect``. There is no comment
  in the code on why we have a ``wexpect.py`` instead of using the PyPI version of
  ``Wexpect``.
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
