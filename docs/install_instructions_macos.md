Installation Instructions (MacOS)
=================================

Install with Installer
----------------------

We now have a proper [installer](https://www.github.com/eoyilmaz/displaycal-py3/releases)
for MacOS and this is the preferred way of running DisplayCAL under MacOS (unless you
want to test the latest code).

> [!WARNING]
> In **MacOS**, after installing DisplayCAL you need to run the following in Terminal:
>
> ```shell
> xattr -dr com.apple.quarantine /Applications/DisplayCAL.app
> ```

Install through PyPI or Build From Source
-----------------------------------------

In macOS, you can install DisplayCAL into an virtual environment through PyPI or build
it from source. Currently we support Python 3.9 to Python 3.13.

Prerequisites
-------------

Install the dependencies through `brew`:

```shell
brew install glib gtk+3 python@3.13
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

> [!TIP]
> If you want to switch to some other branches to test the code you can replace
> `develop` in the previous command with the branch name:
> ```shell
> git checkout 502-ccss-creation-with-i1pro3-does-not-seem-to-work
> ```

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
python3 -m build
pip install dist/DisplayCAL-3.9.*.whl
```

This should install DisplayCAL. To run the UI:

```shell
displaycal
```

Building `DisplayCAL.app`
-------------------------

You can build a proper macOS app to make it easier to run the application.

Firstly install the requirements if you didn't already done it before:

```shell
brew install glib gtk+3 python@3.13
```

Clone the source of DisplayCAL, build and install it:

```shell
cd ~
git clone https://www.github.com/eoyilmaz/displaycal-py3
cd displaycal-py3
make venv build install
source ./.venv/bin/activate
```

Now you can generate the app:

```shell
python3 setup.py py2app
```

That should generate a folder with the name `py2app.macosx-14.0-arm64-py3.13` under the
`dist` folder which should contain another folder with the name `DisplayCAL-3.9.16`
which should contain the `DisplayCAL.app` package.

You can use this directly, by putting it under the `/Applications` of your system.

Creating a `dmg` Image
----------------------

You can generate a `dmg` image so that it is more compact and inline with how the other
macOS applications are distributed.

First put a link to the `Applications` folder for people to easily drag & drop the app
in to their system `Applications` folder:

```shell
cd ~/displaycal-py3/dist/py2app.macosx-14.0-arm64-py3.13/DisplayCAL-3.9.16
ln -s /Applications
```

Use `Disk Utility.app` to generate a `dmg` file, by using the
`File -> New Image -> Image From Folder...` menu and selecting the
`~/displaycal-py3/dist/py2app.macosx-14.0-arm64-py3.13/DisplayCAL-3.9.16` folder.

Now you can rename the `dmg` file to `DisplayCAL-3.9.16-macOS-arm64.dmg` or
`DisplayCAL-3.9.16-macOS-x86.dmg` depending on your macOS architecture.
