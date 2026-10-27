"""Tests for the toolkit-neutral update-check helpers (DisplayCAL/update_check.py).

Covers the pure pieces ported from ``display_cal.py``'s ``is_new_update`` /
``app_update_check`` / ``app_update_confirm`` chain. No display or
QApplication is needed.
"""

from unittest.mock import MagicMock

import pytest
import requests

from DisplayCAL import update_check as uc


class TestFetchLatestReleaseData:
    def test_returns_json_on_success(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "99.0.0", "assets": []}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        assert uc.fetch_latest_release_data() == {"tag_name": "99.0.0", "assets": []}

    def test_returns_none_on_network_error(self, monkeypatch):
        def raise_error(*a, **kw):
            raise requests.RequestException("connection refused")

        monkeypatch.setattr(uc.requests, "get", raise_error)
        assert uc.fetch_latest_release_data() is None

    def test_returns_none_on_http_error(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        assert uc.fetch_latest_release_data() is None

    def test_returns_none_on_bad_json(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("bad json")
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        assert uc.fetch_latest_release_data() is None


class TestResolveAppDownloadUrl:
    @pytest.mark.parametrize(
        "plat,machine,version,expected_filename",
        [
            ("win32", "AMD64", "3.9.0", "DisplayCAL-3.9.0-Windows-x64.exe"),
            ("win32", "ARM64", "3.9.0", "DisplayCAL-3.9.0-Windows-arm64.exe"),
            ("darwin", "arm64", "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
            ("darwin", "aarch64", "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
            ("darwin", "x86_64", "3.9.0", "DisplayCAL-3.9.0-macOS-x86.dmg"),
            ("linux", "x86_64", "3.9.0", "displaycal-3.9.0.tar.gz"),
        ],
    )
    def test_matches_platform_asset(
        self, monkeypatch, plat, machine, version, expected_filename
    ):
        release_data = {
            "assets": [
                {
                    "name": expected_filename,
                    "browser_download_url": f"https://example.com/{expected_filename}",
                }
            ]
        }
        monkeypatch.setattr(uc.sys, "platform", plat)
        monkeypatch.setattr(uc.platform, "machine", lambda: machine)
        assert (
            uc.resolve_app_download_url(release_data, version)
            == f"https://example.com/{expected_filename}"
        )

    def test_returns_none_when_no_matching_asset(self, monkeypatch):
        monkeypatch.setattr(uc.sys, "platform", "linux")
        monkeypatch.setattr(uc.platform, "machine", lambda: "x86_64")
        assert uc.resolve_app_download_url({"assets": []}, "3.9.0") is None


class TestResolveArgyllDownloadUrl:
    @pytest.mark.parametrize(
        "plat,machine,architecture,expected_suffix",
        [
            ("win32", "AMD64", "64bit", "_win64_exe.zip"),
            ("win32", "ARM64", "64bit", "_win_arm64_exe.zip"),
            ("win32", "x86", "32bit", "_win32_exe.zip"),
            ("darwin", "arm64", "64bit", "_macOS11_arm64_bin.tgz"),
            ("darwin", "aarch64", "64bit", "_macOS11_arm64_bin.tgz"),
            ("darwin", "x86_64", "64bit", "_osx10.6_x86_64_bin.tgz"),
            ("linux", "x86_64", "64bit", "_linux_x86_64_bin.tgz"),
            ("linux", "unknown", "32bit", "_linux_x86_bin.tgz"),
        ],
    )
    def test_matches_platform_asset_naming(
        self, monkeypatch, plat, machine, architecture, expected_suffix
    ):
        monkeypatch.setattr(uc.sys, "platform", plat)
        monkeypatch.setattr(uc.platform, "machine", lambda: machine)
        monkeypatch.setattr(uc.platform, "architecture", lambda: (architecture, ""))
        url = uc.resolve_argyll_download_url(
            "3.5.0", "https://github.com/eoyilmaz/argyllcms-binaries"
        )
        assert url == (
            "https://github.com/eoyilmaz/argyllcms-binaries/releases/download/"
            f"3.5.0/Argyll_V3.5.0{expected_suffix}"
        )


class TestCheckAppUpdate:
    def test_returns_result_when_newer_available(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "99.0.0", "assets": []}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        result = uc.check_app_update(current_version=(1, 0, 0))
        assert result is not None
        assert result.component == "app"
        assert result.new_version == "99.0.0"
        assert result.current_version == "1.0.0"
        assert result.release_page_url.endswith("/releases")

    def test_returns_none_when_up_to_date(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "1.0.0", "assets": []}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        assert uc.check_app_update(current_version=(1, 0, 0)) is None

    def test_release_is_newer_than_its_prerelease(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "1.0.0", "assets": []}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        result = uc.check_app_update(current_version=(1, 0, 0), prerelease=True)
        assert result is not None
        assert result.new_version == "1.0.0"

    def test_running_prerelease_is_offered_its_release(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "3.10.0", "assets": []}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        monkeypatch.setattr(uc, "VERSION_TUPLE", (3, 10, 0))
        monkeypatch.setattr(uc, "VERSION_STRING", "3.10.0rc1")
        monkeypatch.setattr(uc, "VERSION_IS_PRERELEASE", True)
        result = uc.check_app_update()
        assert result is not None
        assert result.current_version == "3.10.0rc1"
        assert result.new_version == "3.10.0"

    def test_returns_none_on_fetch_failure(self, monkeypatch):
        monkeypatch.setattr(uc, "fetch_latest_release_data", lambda: None)
        assert uc.check_app_update(current_version=(1, 0, 0)) is None

    def test_returns_none_on_malformed_tag(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "not-a-version"}
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        assert uc.check_app_update(current_version=(1, 0, 0)) is None


class TestCheckArgyllUpdate:
    def test_returns_none_when_undetected(self, monkeypatch):
        monkeypatch.setattr(uc, "get_argyll_latest_version", lambda: "3.0.0")
        assert uc.check_argyll_update([0, 0, 0]) is None
        assert uc.check_argyll_update(None) is None

    def test_returns_none_when_up_to_date(self, monkeypatch):
        monkeypatch.setattr(uc, "get_argyll_latest_version", lambda: "2.3.1")
        assert uc.check_argyll_update([2, 3, 1]) is None

    def test_returns_result_when_newer_available(self, monkeypatch):
        monkeypatch.setattr(uc, "get_argyll_latest_version", lambda: "2.4.0")
        monkeypatch.setattr(uc, "fetch_changelog_html", lambda *a, **kw: "<html/>")
        result = uc.check_argyll_update([2, 3, 1])
        assert result is not None
        assert result.component == "argyll"
        assert result.new_version == "2.4.0"
        assert result.current_version == "2.3.1"
        assert result.download_url is None
        assert result.changelog_html == "<html/>"

    def test_returns_none_on_malformed_latest_version(self, monkeypatch):
        monkeypatch.setattr(uc, "get_argyll_latest_version", lambda: "unknown")
        assert uc.check_argyll_update([2, 3, 1]) is None


class TestFetchChangelogHtml:
    def test_returns_none_when_request_fails(self, monkeypatch):
        monkeypatch.setattr(uc, "http_request", lambda *a, **kw: False)
        assert uc.fetch_changelog_html("example.com", "ChangesSummary.html") is None

    def test_full_page_is_used_and_reformatted(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'<h2>Full page</h2><a href="#foo">bar</a>'
        monkeypatch.setattr(uc, "http_request", lambda *a, **kw: mock_resp)
        html = uc.fetch_changelog_html("example.com", "Argyll/ChangesSummary.html")
        assert html is not None
        assert "<strong>Full page</strong>" in html
        assert 'href="https://example.com/#foo"' in html


class TestReleaseNotesHtml:
    def test_renders_release_body_markdown(self):
        html = uc.release_notes_html({"body": "## Highlights\n\n- **New** `Qt` UI"})
        assert html is not None
        assert "<p><strong>Highlights</strong></p>" in html
        assert "<li><strong>New</strong> <code>Qt</code> UI</li>" in html

    @pytest.mark.parametrize("data", [{}, {"body": ""}, {"body": None}])
    def test_returns_none_without_body(self, data):
        assert uc.release_notes_html(data) is None

    def test_check_app_update_uses_release_body(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "tag_name": "99.0.0",
            "assets": [],
            "body": "- Fixed things",
        }
        monkeypatch.setattr(uc.requests, "get", lambda *a, **kw: mock_resp)
        result = uc.check_app_update(current_version=(1, 0, 0))
        assert result is not None
        assert "<li>Fixed things</li>" in result.changelog_html
