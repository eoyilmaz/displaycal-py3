"""Toolkit-neutral application / ArgyllCMS update-check logic — Qt port support.

Ports the non-dialog pieces of ``display_cal.py``'s ``is_new_update`` /
``app_update_check`` / ``app_update_confirm`` chain (mirroring the
``preflight_checks.py`` / ``profile_finish.py`` precedent of a plain,
Qt-free module the still-shipping wx path could delegate to). This module is
a **fresh copy**, not an extraction-and-delegate: ``display_cal.py`` imports
``wx`` at module scope, so it can never be imported from the pure-Qt process,
and its ``is_new_update`` / ``get_download_url`` already have dedicated tests
(``tests/test_display_cal.py``) that monkeypatch ``display_cal.requests`` /
``display_cal.sys.platform`` / ``display_cal.platform.machine`` directly on
that module's namespace — a delegating wrapper would silently break them.
Both copies now call the same GitHub / ArgyllCMS APIs; they are expected to
stay in sync by inspection (the logic is small and unlikely to change).

Deliberately not reproduced (only reachable from the wx-side callers, which
never invoke it this way from the Qt startup path either):

* the snapshot/beta release channel (``snapshot=True``) — every wx call site
  that reaches the silent startup check passes ``snapshot=False``; only the
  wx update dialog's own "not up to date, and not a snapshot build" branch
  ever recurses into checking the snapshot channel afterwards, a self-chained
  check this module does not reproduce (a manual "Check for updates" click
  from the Qt UI only checks the stable release);
* the ZeroInstall packaging path (``zeroinstall``, hard-coded ``False`` in wx
  already);
* the in-app auto-download-and-run-the-installer flow
  (``app_update_confirm``'s ``worker.start(consumer, worker.download, ...)``
  branch) for the *update-available* dialogs — the Qt
  ``_UpdateAvailableDialog`` offers a direct asset download URL (opened in
  the browser) or a "go to website" fallback instead of driving
  Argyll/DisplayCAL installers itself. The *missing*-ArgyllCMS startup
  prompt (``MainWindow._prompt_missing_argyll``) is a separate flow and
  does drive a real in-app download + extract, via
  :func:`resolve_argyll_download_url` below plus a small Qt-only
  ``_ArgyllDownloadThread`` (``main_window.py``) — installing ArgyllCMS in
  the first place is table-stakes for a working app, unlike an optional
  version bump.
"""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import dataclass

import requests

from DisplayCAL.argyll import get_argyll_latest_version
from DisplayCAL.changelog import markdown_to_html
from DisplayCAL.meta import (
    ARGYLL_CHANGELOG_DOMAIN,
    ARGYLL_CHANGELOG_PATH,
    DEVELOPMENT_HOME_PAGE,
    DOMAIN,
    GITHUB_API_URL,
    VERSION_IS_PRERELEASE,
    VERSION_STRING,
    VERSION_TUPLE,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.worker import http_request

#: ArgyllCMS's own project site, used as the "go to website" fallback since
#: Argyll releases aren't hosted on the DisplayCAL GitHub repo.
ARGYLL_HOME_PAGE = "https://www.argyllcms.com/"


@dataclass
class UpdateCheckResult:
    """A newer version was found for one component ("app" or "argyll")."""

    component: str
    current_version: str
    new_version: str
    changelog_html: str | None
    #: Direct release-asset URL for the current platform, if resolvable.
    download_url: str | None
    #: Fallback "go to website" URL, always set.
    release_page_url: str


def fetch_latest_release_data(timeout: int = 10) -> dict | None:
    """Fetch the latest GitHub release payload for DisplayCAL itself.

    Returns:
        dict | None: The parsed JSON payload, or ``None`` on any network or
            parsing failure (printed, not raised, matching ``is_new_update``).
    """
    headers = {"User-Agent": "DisplayCAL-updater"}
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/releases/latest", headers=headers, timeout=timeout
        )
        response.raise_for_status()
    except requests.RequestException as exception:
        print(f"Error checking for updates: Network error - {exception}")
        return None
    try:
        return response.json()
    except ValueError as exception:
        print(f"Error checking for updates: Parsing error - {exception}")
        return None


def resolve_app_download_url(release_data: dict, newversion: str) -> str | None:
    """Return the release asset URL matching the current platform, if any.

    Toolkit-neutral port of ``display_cal.get_download_url``.
    """
    if sys.platform == "win32":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            filename = f"{APPNAME}-{newversion}-Windows-arm64.exe"
        else:
            filename = f"{APPNAME}-{newversion}-Windows-x64.exe"
    elif sys.platform == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            filename = f"{APPNAME}-{newversion}-macOS-arm64.dmg"
        else:
            filename = f"{APPNAME}-{newversion}-macOS-x86.dmg"
    else:
        filename = f"{APPNAME.lower()}-{newversion}.tar.gz"
    for asset in release_data.get("assets", []):
        if asset.get("name") == filename:
            return asset.get("browser_download_url")
    return None


def resolve_argyll_download_url(newversion: str, domain: str) -> str:
    """Return the ArgyllCMS release archive URL for the current platform.

    Toolkit-neutral port of the ArgyllCMS branch of wx's
    ``app_update_confirm`` (``display_cal.py``): same
    ``argyll.domain``-relative GitHub Releases layout and per-platform
    suffix table, simplified to ``platform.machine()`` detection (no
    Windows registry lookup) like :func:`resolve_app_download_url`.
    Confirmed against the real ``eoyilmaz/argyllcms-binaries`` release
    assets, which are named exactly ``Argyll_V{version}{suffix}``.

    Args:
        newversion: The ArgyllCMS version string (e.g. ``"3.5.0"``).
        domain: The ``argyll.domain`` config value (a GitHub repo URL).
    """
    machine = platform.machine().lower()
    if sys.platform == "win32":
        if machine in ("arm64", "aarch64"):
            suffix = "_win_arm64_exe.zip"
        elif machine in ("amd64", "x86_64"):
            suffix = "_win64_exe.zip"
        else:
            suffix = "_win32_exe.zip"
    elif sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            suffix = "_macOS11_arm64_bin.tgz"
        else:
            suffix = "_osx10.6_x86_64_bin.tgz"
    elif machine in ("x86_64", "amd64") or platform.architecture()[0] == "64bit":
        suffix = "_linux_x86_64_bin.tgz"
    else:
        suffix = "_linux_x86_bin.tgz"
    return f"{domain}/releases/download/{newversion}/Argyll_V{newversion}{suffix}"


def _format_changelog(html: str, domain: str) -> str:
    """Rewrite anchor-only ``href``s and demote heading tags, matching wx."""
    html = re.sub(
        re.compile(r"<h\d>(.+?)</h\d>", flags=re.I | re.S),
        r"<p><strong>\1</strong></p>",
        html,
    )
    return re.sub(
        re.compile(r'href="(#[^"]+)"', flags=re.I),
        rf'href="https://{domain}/\1"',
        html,
    )


def fetch_changelog_html(domain: str, path: str) -> str | None:
    """Fetch and lightly reformat a changelog page (ArgyllCMS's).

    Args:
        domain: The host to request from.
        path: The changelog path (e.g. ``"Argyll/ChangesSummary.html"``).
    """
    resp = http_request(None, domain, "GET", "/" + path, silent=True)
    if not resp:
        return None
    return _format_changelog(resp.read().decode("utf-8", "replace"), domain)


def release_notes_html(release_data: dict) -> str | None:
    """Render a GitHub release's Markdown notes as a changelog page.

    Args:
        release_data: The GitHub release payload (``fetch_latest_release_data``).

    Returns:
        str | None: The HTML page, or None if the release has no notes.
    """
    body = release_data.get("body")
    if not body:
        return None
    html = (
        "<!DOCTYPE html><html><head><title></title></head>"
        f"<body>{markdown_to_html(body)}</body></html>"
    )
    return _format_changelog(html, DOMAIN)


def check_app_update(
    current_version: tuple[int, ...] | None = None,
    prerelease: bool | None = None,
) -> UpdateCheckResult | None:
    """Check for a newer DisplayCAL release.

    Args:
        current_version: Defaults to the running ``VERSION_TUPLE``.
        prerelease: Whether ``current_version`` is a pre-release, which the
            release of the same version is newer than. Defaults to
            ``VERSION_IS_PRERELEASE`` for the running version, False otherwise.

    Returns:
        UpdateCheckResult | None: None if up to date or the check failed.
    """
    print("Checking for updates...")
    data = fetch_latest_release_data()
    if data is None:
        return None
    try:
        latest = tuple(int(n) for n in data["tag_name"].split("."))
    except (KeyError, ValueError, IndexError, AttributeError, TypeError) as exception:
        print(f"Error checking for updates: Parsing error - {exception}")
        return None
    if prerelease is None:
        prerelease = current_version is None and VERSION_IS_PRERELEASE
    current = tuple(current_version or VERSION_TUPLE)[:3]
    if latest < current or (latest == current and not prerelease):
        print("No new updates available.")
        return None
    print("New updates available!")
    newversion = ".".join(str(n) for n in latest)
    return UpdateCheckResult(
        component="app",
        current_version=(
            VERSION_STRING
            if current_version is None
            else ".".join(str(n) for n in current)
        ),
        new_version=newversion,
        changelog_html=release_notes_html(data),
        download_url=resolve_app_download_url(data, newversion),
        release_page_url=f"{DEVELOPMENT_HOME_PAGE}/releases",
    )


def check_argyll_update(
    current_version: list[int] | None,
) -> UpdateCheckResult | None:
    """Check for a newer ArgyllCMS release.

    Args:
        current_version: The currently detected Argyll version (``Worker
            .argyll_version``, e.g. ``[0, 0, 0]`` when undetected). None or
            an all-zero version skips the check (nothing to compare against).

    Returns:
        UpdateCheckResult | None: None if up to date, undetected, or the
            check failed.
    """
    if not current_version or tuple(current_version) <= (0, 0, 0):
        return None
    latest_str = get_argyll_latest_version()
    try:
        latest = tuple(int(n) for n in latest_str.split("."))
    except (ValueError, AttributeError, TypeError):
        return None
    current = tuple(current_version)
    if latest <= current:
        return None
    return UpdateCheckResult(
        component="argyll",
        current_version=".".join(str(n) for n in current),
        new_version=latest_str,
        changelog_html=fetch_changelog_html(
            ARGYLL_CHANGELOG_DOMAIN, ARGYLL_CHANGELOG_PATH
        ),
        download_url=None,
        release_page_url=ARGYLL_HOME_PAGE,
    )
