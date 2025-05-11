# ----------------------------------------------------------------------
# Name:        wxversion
# Purpose:     Allows a wxPython program to search for alternate
#              installations of the wxPython packages and modify sys.path
#              so they will be found when "import wx" is done.
#
# Author:      Robin Dunn
#
# Created:     24-Sept-2004
# RCS-ID:      $Id$
# Copyright:   (c) 2004 by Total Control Software
# Licence:     wxWindows license
#
# 2019-05      Updated to find Phoenix versions and never override first
#              entry in sys.path (usually current dir) - fhoech
# ----------------------------------------------------------------------

"""If you have more than one version of wxPython installed this module
allows your application to choose which version of wxPython will be
imported when it does 'import wx'.  The main function of this module
is `select` and you use it like this::

    import wxversion
    wxversion.select('2.4')
    import wx

Or additional build options can also be selected, although they will
not be required if they are not installed, like this::

    import wxversion
    wxversion.select('2.5.3-unicode')
    import wx

Or you can require an exact match on the build options like this::

    import wxversion
    wxversion.select('2.5.3-unicode', options_required=True)
    import wx

Finally you can also specify a collection of versions that are allowed
by your application, like this::

    import wxversion
    wxversion.select(['2.5.4', '2.5.5', '2.6'])
    import wx


Of course the default wxPython version can also be controlled by
setting PYTHONPATH or by editing the wx.pth path configuration file,
but using wxversion will allow an application to manage the version
selection itself rather than depend on the user to setup the
environment correctly.

It works by searching the sys.path for directories matching wx-* and
then comparing them to what was passed to the select function.  If a
match is found then that path is inserted into sys.path.

NOTE: If you are making a 'bundle' of your application with a tool
like py2exe then you should *not* use the wxversion module since it
looks at the filesystem for the directories on sys.path, it will fail
in a bundled environment.  Instead you should simply ensure that the
version of wxPython that you want is found by default on the sys.path
when making the bundled version by setting PYTHONPATH.  Then that
version will be included in your bundle and your app will work as
expected.  Py2exe and the others usually have a way to tell at runtime
if they are running from a bundle or running raw, so you can check
that and only use wxversion if needed.  For example, for py2exe::

    if not hasattr(sys, 'frozen'):
        import wxversion
        wxversion.select('2.5')
    import wx

More documentation on wxversion and multi-version installs can be
found at: http://wiki.wxpython.org/index.cgi/MultiVersionInstalls

"""

import fnmatch
import glob
import os
import re
import sys
from typing import Union

_SELECTED = None
_EM_DEBUG = 0
UPDATE_URL = "https://wxPython.org/"
_WX_VERSION_PATTERN = "wx-[0-9].*"
_WX_VERSION_PATTERN_PHOENIX = "wxPython-[0-9].*.egg"


class VersionError(Exception):
    pass


class AlreadyImportedError(VersionError):
    pass


def select(versions, options_required=False):
    """Search for a wxPython installation that matches version.

    If one is found then sys.path is modified so that version will be imported
    with a 'import wx', otherwise a VersionError exception is raised. This
    function should only be called once at the beginning of the application
    before wxPython is imported.

    Args:
        versions: Specifies the version to look for, it can either be a string
            or a list of strings. Each string is compared to the installed
            wxPythons and the best match is inserted into the sys.path,
            allowing an 'import wx' to find that version.

            The version string is composed of the dotted version number (at
            least 2 of the 4 components) optionally followed by hyphen ('-')
            separated options (wx port, unicode/ansi, flavour, etc.) A match is
            determined by how much of the installed version matches what is
            given in the version parameter. If the version number components
            don't match then the score is zero, otherwise the score is
            increased for every specified optional component that is specified
            and that matches.

            Please note, however, that it is possible for a match to be
            selected that doesn't exactly match the versions requested. The
            only component that is required to be matched is the version
            number. If you need to require a match on the other components as
            well, then please use the optional ``options_required`` parameter
            described next.

        options_required: Allows you to specify that the other components of
            the version string (such as the port name or character type) are
            also required to be present for an installed version to be
            considered a match. Using this parameter allows you to change the
            selection from a soft, as close as possible match to a hard, exact
            match.
    """
    if isinstance(versions, str):
        versions = [versions]

    global _SELECTED
    if _SELECTED is not None:
        # A version was previously selected, ensure that it matches
        # this new request
        for ver in versions:
            if _SELECTED.score(_wxPackageInfo(ver), options_required) > 0:
                return
        # otherwise, raise an exception
        raise VersionError(
            "A previously selected wx version does not match the new request."
        )

    # If we get here then this is the first time wxversion is used,
    # ensure that wxPython hasn't been imported yet.
    if "wx" in sys.modules or "wxPython" in sys.modules:
        raise AlreadyImportedError(
            "wxversion.select() must be called before wxPython is imported"
        )

    # Look for a matching version and manipulate the sys.path as
    # needed to allow it to be imported.
    installed = _find_installed(True)
    best_match = _get_best_match(installed, versions, options_required)

    if best_match is None:
        raise VersionError("Requested version of wxPython not found")

    if best_match.pathname not in sys.path:
        sys.path.insert(1, best_match.pathname)
        # q.v. Bug #1409256
        path64 = re.sub("/lib/", "/lib64/", best_match.pathname)
        if path64 != best_match.pathname and os.path.isdir(path64):
            sys.path.insert(1, path64)
    _SELECTED = best_match


def ensure_minimal(min_version, options_required=False) -> None:
    """Ensure the default wxPython version is >= `minVersion`.

    If not, attempt to find an installed version >= `minVersion`. If none are
    found, prompt the user to download a compatible version  and exit the
    application.

    Args:
        min_version (str): The minimum required version of wxPython.
        options_required (bool): If True, require exact match on options.

    Raises:
        AlreadyImportedError: If wxPython has already been imported.
        VersionError: If no matching version is found and the user declines to
            download.
    """
    assert isinstance(min_version, str)

    # ensure that wxPython hasn't been imported yet.
    if "wx" in sys.modules or "wxPython" in sys.modules:
        raise AlreadyImportedError(
            "wxversion.ensureMinimal() must be called before wxPython is imported"
        )

    best_match = None
    minv = _wxPackageInfo(min_version)

    # check the default version first
    default_path = _find_default()
    if default_path:
        defv = _wxPackageInfo(default_path, True)
        if defv >= minv and minv.check_options(defv, options_required):
            best_match = defv

    # if still no match then check look at all installed versions
    if best_match is None:
        installed = _find_installed()
        # The list is in reverse sorted order, so find the first
        # one that is big enough and optionally matches the
        # options
        for inst in installed:
            if inst >= minv and minv.check_options(inst, options_required):
                best_match = inst
                break

    # if still no match then prompt the user
    if best_match is None:
        if _EM_DEBUG:  # We'll do it this way just for the test code below
            raise VersionError("Requested version of wxPython not found")

        import webbrowser

        import wx

        versions = "\n".join(["      " + ver for ver in get_installed()])
        app = wx.App()
        result = wx.MessageBox(
            "This application requires a version of wxPython "
            f"greater than or equal to {min_version}, but a matching version "
            "was not found.\n\n"
            f"You currently have these version(s) installed:\n{versions}\n\n"
            "Would you like to download a new version of wxPython?\n",
            "wxPython Upgrade Needed",
            style=wx.YES_NO,
        )
        if result == wx.YES:
            webbrowser.open(UPDATE_URL)
        app.MainLoop()
        sys.exit()

    if best_match.pathname not in sys.path:
        sys.path.insert(1, best_match.pathname)
        # q.v. Bug #1409256
        path64 = re.sub("/lib/", "/lib64/", best_match.pathname)
        if path64 != best_match.pathname and os.path.isdir(path64):
            sys.path.insert(1, path64)
    global _SELECTED
    _SELECTED = best_match


def check_installed(versions : list[str], options_required : bool =False):
    """Check if a version of wxPython installed that matches one of the versions given.

    This can be used to determine if calling `select` will succeed or not.

    Args:
        versions (list[str]): Same as in `select`, either a string or a list
            of strings specifying the version(s) to check for.
        options_required (bool): Same as in `select`.

    Returns:
        bool: True if a matching version is found, False otherwise.
    """
    if isinstance(versions, str):
        versions = [versions]
    installed = _find_installed()
    bestMatch = _get_best_match(installed, versions, options_required)
    return bestMatch is not None


def get_installed() -> list[str]:
    """Return a list of installed wxPython versions as strings.
    
    Returns:
        list[str]: A list of installed wxPython versions in the format
            "wx-<version>".
    """
    installed = _find_installed()
    return [p.base.split("-", 1).pop() for p in installed]


def _get_best_match(installed, versions, options_required):
    """Find the best match for the given versions in the installed wxPython packages.
    
    Args:
        installed (list[_wxPackageInfo]): List of installed wxPython packages.
        versions (list[str]): List of version strings to match against.
        options_required (bool): Whether options are required for a match.
    
    Returns:
        _wxPackageInfo: The best matching wxPython package, or None if no match
            is found.
    """
    best_match = None
    best_score = 0
    for pkg in installed:
        for ver in versions:
            score = pkg.score(_wxPackageInfo(ver), options_required)
            if score > best_score:
                best_match = pkg
                best_score = score
    return best_match


def _find_installed(removeExisting=False):
    installed = []
    toRemove = []
    for pth in sys.path:
        # empty means to look in the current dir
        if not pth:
            pth = "."

        # skip it if it's not a package dir
        if not os.path.isdir(pth):
            continue

        base = os.path.basename(pth)

        # if it's a wx path that's already in the sys.path then mark
        # it for removal and then skip it
        if fnmatch.fnmatchcase(base, _WX_VERSION_PATTERN) or fnmatch.fnmatchcase(
            base, _WX_VERSION_PATTERN_PHOENIX
        ):
            toRemove.append(pth)
            continue

        # now look in the dir for matching subdirs
        for name in glob.glob(os.path.join(pth, _WX_VERSION_PATTERN)) + glob.glob(
            os.path.join(pth, _WX_VERSION_PATTERN_PHOENIX)
        ):
            # make sure it's a directory
            if not os.path.isdir(name):
                continue
            # and has a wx subdir
            if not os.path.exists(os.path.join(name, "wx")):
                continue
            installed.append(_wxPackageInfo(name, True))

        # Phoenix
        name = os.path.join(pth, "wx")
        phoenix_version_py = os.path.join(name, "__version__.py")
        if os.path.isfile(phoenix_version_py):
            version_info = {}
            with open(phoenix_version_py, "rb") as f:
                phoenix_version = f.read()
            exec(
                compile(phoenix_version, phoenix_version_py, "exec"),
                {},
                version_info,
            )
            if version_info["VERSION"] >= (4,):
                pinfo = _wxPackageInfo(
                    "{}-{}".format(name, version_info["VERSION_STRING"]), True
                )
                pinfo.pathname = pth
                installed.append(pinfo)

    if removeExisting:
        for rem in toRemove:
            del sys.path[sys.path.index(rem)]

    installed.sort()
    installed.reverse()
    return installed


def _find_default() -> Union[None, str]:
    """Scan sys.path for a directory matching _pattern or a wx.pth file.

    Returns:
        Union[None, str]: The path to the wxPython installation if found,
            otherwise None.
    """
    for pth in sys.path:
        # empty means to look in the current dir
        if not pth:
            pth = "."

        # skip it if it's not a package dir
        if not os.path.isdir(pth):
            continue

        # does it match the pattern?
        base = os.path.basename(pth)
        if fnmatch.fnmatchcase(base, _WX_VERSION_PATTERN) or fnmatch.fnmatchcase(
            base, _WX_VERSION_PATTERN_PHOENIX
        ):
            return pth

    for pth in sys.path:
        if not pth:
            pth = "."
        if not os.path.isdir(pth):
            continue
        if os.path.exists(os.path.join(pth, "wx.pth")):
            with open(os.path.join(pth, "wx.pth")) as f:
                base = f.read()
            return os.path.join(pth, base)

    return None


class _wxPackageInfo:
    """A class to hold information about a wxPython package."""

    def __init__(self, pathname, stripFirst=False):
        self.pathname = pathname
        self.base = os.path.basename(pathname)
        segments = self.base.split("-")
        if stripFirst:
            segments = segments[1:]
        self.version = tuple(segments[0].split("."))
        self.options = segments[1:]

    def score(self, other, options_required):
        score = 0

        # whatever number of version components given in other must
        # match exactly
        minlen = min(len(self.version), len(other.version))
        if self.version[:minlen] != other.version[:minlen]:
            return 0
        score += 1

        # check for matching options, if options_required then the
        # options are not optional ;-)
        for opt in other.options:
            if opt in self.options:
                score += 1
            elif options_required:
                return 0

        return score

    def check_options(self, other, options_required):
        # if options are not required then this always succeeds
        if not options_required:
            return True
        # otherwise, if we have any option not present in other, then
        # the match fails.
        return all(opt in other.options for opt in self.options)

    def __lt__(self, other):
        return self.version < other.version or (
            self.version == other.version and self.options < other.options
        )

    def __le__(self, other):
        return self.version <= other.version or (
            self.version == other.version and self.options <= other.options
        )

    def __gt__(self, other):
        return self.version > other.version or (
            self.version == other.version and self.options > other.options
        )

    def __ge__(self, other):
        return self.version >= other.version or (
            self.version == other.version and self.options >= other.options
        )

    def __eq__(self, other):
        return self.version == other.version and self.options == other.options
