

Installation Instructions (Linux)
=================================

Although, there are currently no RPM, DEB or other common packages to install DisplayCAL
directly under Linux, some distros supply recent DisplayCAL versions in their package
management systems. Please search for them first.

Otherwise you can install DisplayCAL under Linux pretty easily.

Prerequisites
-------------

In Linux, you can install DisplayCAL into an virtual environment through PyPI or build
it from source. Currently we support Python 3.8 to Python 3.13.

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
# Debian installs (Debian, Ubuntu etc.)
apt-get install build-essential dbus libglib2.0-dev pkg-config libgtk-3-dev libxxf86vm-dev python3-dev python3-venv

# Fedora core installs (Fedora, Rocky, CentOS etc.)
dnf install gcc glibc-devel dbus pkgconf gtk3-devel libXxf86vm-devel python3-devel python3-virtualenv

# OpenSuse
zypper install gcc12 gcc12-c++ git-core glibc-devel dbus-1 pkgconf gtk3-devel libXxf86vm-devel make python3-devel python3-virtualenv
```

Because Python 3 is generally build with gcc 12 it is better to update your alternatives
to use the 12th version of gcc/g++.

```shell
sudo update-alternatives --config gcc
# select gcc-12
sudo update-alternatives --config g++
# select g++-12
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
source ~/venv-diplaycal/bin/activate
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
pip install dist/DisplayCAL-3.9.*.whl
```

This should install DisplayCAL. To run the UI:

```shell
displaycal
```