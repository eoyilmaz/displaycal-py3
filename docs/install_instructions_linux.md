

Installation Instructions (Linux)
=================================

ArgyllCMS Requirement
----------------------

DisplayCAL relies on [ArgyllCMS](https://www.argyllcms.com/) to talk to your
measurement instrument and take the actual readings, it is not bundled with any of
the packages/installers or install methods described below and needs to be obtained
separately.

You don't have to grab it upfront though. The first time you launch DisplayCAL and it
can't find a working ArgyllCMS installation, it will offer to either **download** a
matching build for you automatically (from
[eoyilmaz/argyllcms-binaries](https://github.com/eoyilmaz/argyllcms-binaries/releases)),
or **browse** to an existing installation already on your system.

If you'd rather install it yourself first (e.g. through your distro's package
manager, or manually from the
[ArgyllCMS releases page](https://github.com/eoyilmaz/argyllcms-binaries/releases)),
that works too, DisplayCAL will pick it up automatically if it's on your `PATH`.
Otherwise, point DisplayCAL at its `bin` folder via *File -> Locate ArgyllCMS
executables...* whenever you need to change it.

Install with Package
---------------------

We publish DEB, RPM, Flatpak and AppImage packages for each
[release](https://www.github.com/eoyilmaz/displaycal-py3/releases), and this is the
preferred way of running DisplayCAL under Linux (unless you want to test the latest
code). Pick whichever matches your distro/preference:

* `DisplayCAL-<version>-Linux-amd64.deb`, for Debian/Ubuntu and other DEB-based distros:

  ```shell
  sudo apt install ./DisplayCAL-<version>-Linux-amd64.deb
  ```

* `DisplayCAL-<version>-Linux-x86_64.rpm`, for Fedora and other RPM-based distros
  using Fedora's package names:

  ```shell
  sudo dnf install ./DisplayCAL-<version>-Linux-x86_64.rpm
  ```

  Both the DEB and the RPM need Python 3.11 to 3.14 and glibc 2.34 or newer (Debian
  12, Ubuntu 24.04, Fedora or later). wxPython and dbus-python are installed from your
  distro's own repositories, every other Python dependency is bundled in the package
  itself, so installing it doesn't download anything from PyPI or compile anything.

* `DisplayCAL-<version>-Linux-x86_64.flatpak`, distro-independent:

  ```shell
  flatpak install ./DisplayCAL-<version>-Linux-x86_64.flatpak
  ```

* `DisplayCAL-<version>-Linux-x86_64.AppImage`, distro-independent, no installation
  needed:

  ```shell
  chmod +x DisplayCAL-<version>-Linux-x86_64.AppImage
  ./DisplayCAL-<version>-Linux-x86_64.AppImage
  ```

Also, some distros supply recent DisplayCAL versions in their own package management
systems, please search for them first if you'd rather use your distro's native
packaging.

If none of these suit your needs, you can install DisplayCAL under Linux pretty easily
through PyPI or by building it from source, as described below.

Prerequisites
-------------

In Linux, you can install DisplayCAL into a virtual environment through PyPI or build
it from source. Currently we support Python 3.11 to Python 3.14.

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
# Debian installs
apt-get install build-essential dbus libglib2.0-dev pkg-config libgtk-3-dev libxxf86vm-dev python3-dev python3-venv

# Fedora core installs
dnf install gcc glibc-devel dbus pkgconf gtk3-devel libXxf86vm-devel python3-devel python3-virtualenv
```

> [!NOTE]
> Note, if your system's default python is outside the supported range you will need to
> install a supported version and its related devel package.

Install through PyPI
--------------------

Installing through PyPI is straight forward. We highly suggest using a virtual
environment and not installing it to the system python:

Create a virtual environment:

```shell
cd ~
python -m venv venv-displaycal
source venv-displaycal/bin/activate
pip install displaycal
```

and now you can basically run `displaycal`:

```shell
displaycal
```

If you close the current terminal and run a new one, you need to activate the virtual
environment before calling `displaycal`:

```shell
source ~/venv-displaycal/bin/activate
displaycal
```

Build From Source (Makefile Workflow)
-------------------------------------

To test the latest code you can build DisplayCAL from its source. To do that:

Pull the source:

```shell
cd ~
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
make venv build install
```

The build step assumes your system has a `python3` binary available that is
within the correct range. If your system `python3` is not supported and you
installed a new one, you can try passing it to the build command:

```shell
$ SYSTEM_PYTHON=python3.11 make venv build install
```

If this errors out for you, you can follow the
[Build From Source (Manual)](#build-from-source-manual) section below.

Otherwise, this should install DisplayCAL. To run the UI:

```shell
make launch
```

Build From Source (Manual)
--------------------------

If the `makefile` workflow doesn't work for you for some reason, you can setup the
virtual environment manually. Ensure the python binary you're using is supported:

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m build
pip install dist/displaycal-*.whl
```

This should install DisplayCAL. To run the UI:

```shell
displaycal
```
