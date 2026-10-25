Installation Instructions (MacOS)
=================================

ArgyllCMS Requirement
----------------------

DisplayCAL relies on [ArgyllCMS](https://www.argyllcms.com/) to talk to your
measurement instrument and take the actual readings, it is not bundled with the
installer or any of the install methods described below and needs to be obtained
separately.

You don't have to grab it upfront though. The first time you launch DisplayCAL and it
can't find a working ArgyllCMS installation, it will offer to either **download** a
matching build for you automatically (from
[eoyilmaz/argyllcms-binaries](https://github.com/eoyilmaz/argyllcms-binaries/releases)),
**browse** to an existing installation already on your system, or use a
Homebrew-installed copy if one is detected (`brew install argyll-cms`).

If you'd rather install it yourself first, that works too, DisplayCAL will pick it up
automatically if it's on your `PATH` (including via Homebrew). Otherwise, point
DisplayCAL at its `bin` folder via *DisplayCAL -> Locate ArgyllCMS executables...*
whenever you need to change it.

Install with Installer
----------------------

We now have a proper [installer](https://www.github.com/eoyilmaz/displaycal-py3/releases)
for MacOS and this is the preferred way of running DisplayCAL under MacOS (unless you
want to test the latest code). Each release publishes two disk images, pick the one
matching your Mac:

* `DisplayCAL-<version>-macOS-arm64.dmg`, for Apple Silicon Macs (M1 and newer)
* `DisplayCAL-<version>-macOS-x86_64.dmg`, for Intel Macs

> [!NOTE]
> ArgyllCMS 3.5.0 adds native Apple Silicon binaries
> (`Argyll_V3.5.0_macOS11_arm64_bin.tgz`). Intel macOS still uses
> `Argyll_V3.5.0_osx10.6_x86_64_bin.tgz`. DisplayCAL download handling supports both.

> [!WARNING]
> In **MacOS**, after installing DisplayCAL you need to run the following in Terminal:
>
> ```shell
> xattr -dr com.apple.quarantine /Applications/DisplayCAL
> ```

Install through PyPI or Build From Source
-----------------------------------------

In macOS, you can install DisplayCAL into a virtual environment through PyPI or build
it from source. Currently we support Python 3.11 to Python 3.14.

Prerequisites
-------------

Install the dependencies through `brew`:

```shell
brew install glib gtk+3 python@3.14
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
SYSTEM_PYTHON=python3.11 make venv build install
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

Building `DisplayCAL.app`
-------------------------

You can build a proper macOS app to make it easier to run the application.

Firstly install the requirements if you didn't already done it before:

```shell
brew install glib gtk+3 python@3.14
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
python native_build.py py2app
```

That should generate a folder under `dist` with a name similar to
`py2app.macosx-<macOS-version>-<arch>-py<python-version>`, containing a
`DisplayCAL-<version>` folder with the `DisplayCAL.app` package.

You can use this directly, by putting it under the `/Applications` of your system.

Creating a `dmg` Image
----------------------

You can generate a `dmg` image so that it is more compact and inline with how the other
macOS applications are distributed.

First put a link to the `Applications` folder for people to easily drag & drop the app
in to their system `Applications` folder:

```shell
cd ~/displaycal-py3/dist/py2app.macosx-*/DisplayCAL-*
ln -s /Applications
```

Use `Disk Utility.app` to generate a `dmg` file, by using the
`File -> New Image -> Image From Folder...` menu and selecting the
`~/displaycal-py3/dist/py2app.macosx-*/DisplayCAL-*` folder.

Now you can rename the `dmg` file to `DisplayCAL-<version>-macOS-arm64.dmg` or
`DisplayCAL-<version>-macOS-x86_64.dmg` depending on your macOS architecture.
