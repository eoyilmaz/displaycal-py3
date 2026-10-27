"""Tests for the Markdown changelog helpers (DisplayCAL/changelog.py)."""

from pathlib import Path

import pytest

from _native_build.appdata import strip_non_linux_sections
from _native_build.templates import format_changelog
from DisplayCAL.changelog import CHANGELOG_FILENAME, get_latest_entry, markdown_to_html

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / CHANGELOG_FILENAME


class TestGetLatestEntry:
    def test_returns_first_version_section_without_heading(self):
        markdown = (
            "# Changelog\n\nIntro.\n\n"
            "## 2.0.0 - Unreleased\n\n### Fixes\n\n- New fix\n\n"
            "## [1.0.0](https://example.com) - 2020-01-01\n\n- Old fix\n"
        )
        assert get_latest_entry(markdown) == "### Fixes\n\n- New fix"

    def test_returns_none_without_version_sections(self):
        assert get_latest_entry("# Changelog\n\nNothing yet.\n") is None

    def test_real_changelog_has_a_latest_entry(self):
        entry = get_latest_entry(CHANGELOG_PATH.read_text(encoding="utf-8"))
        assert entry
        assert not entry.startswith("## ")


class TestMarkdownToHtml:
    @pytest.mark.parametrize(
        "markdown, expected",
        [
            ("### Title", "<h3>Title</h3>"),
            ("Some text\nwrapped", "<p>Some text wrapped</p>"),
            ("**bold** and *it* and _it_", "<p><strong>bold</strong> and <em>it</em> and <em>it</em></p>"),
            ("`a < b`", "<p><code>a &lt; b</code></p>"),
            ("``rst_style``", "<p><code>rst_style</code></p>"),
            ("[#1](https://example.com/1)", '<p><a href="https://example.com/1">#1</a></p>'),
            ("see https://example.com/x.", '<p>see <a href="https://example.com/x">https://example.com/x</a>.</p>'),
            ("a <b> & c", "<p>a &lt;b&gt; &amp; c</p>"),
            ("snake_case_name stays", "<p>snake_case_name stays</p>"),
            ("---", "<hr />"),
        ],
    )
    def test_inline_and_simple_blocks(self, markdown, expected):
        assert markdown_to_html(markdown) == expected

    def test_nested_lists(self):
        markdown = "- one\n  - one.a\n  - one.b\n- two\n\n1. first\n2. second"
        assert markdown_to_html(markdown) == (
            "<ul><li>one<ul><li>one.a</li><li>one.b</li></ul></li><li>two</li></ul>\n"
            "<ol><li>first</li><li>second</li></ol>"
        )

    def test_list_item_continuation_line(self):
        assert markdown_to_html("- a long\n  item") == "<ul><li>a long item</li></ul>"

    def test_paragraph_followed_by_list(self):
        assert markdown_to_html("**Name**\n- item") == (
            "<p><strong>Name</strong></p>\n<ul><li>item</li></ul>"
        )

    def test_fenced_code_is_escaped_verbatim(self):
        assert markdown_to_html("```shell\nxattr -dr **x** <y>\n```") == (
            "<pre><code>xattr -dr **x** &lt;y&gt;</code></pre>"
        )

    def test_github_alert_blockquote(self):
        assert markdown_to_html("> [!WARNING]\n> Be careful") == (
            "<blockquote><p><strong>Warning</strong></p>\n<p>Be careful</p></blockquote>"
        )

    def test_real_changelog_renders(self):
        html = markdown_to_html(CHANGELOG_PATH.read_text(encoding="utf-8"))
        assert html.count("<h2>") > 10
        assert "<pre>" not in html


class TestAppStreamChangelog:
    def test_strip_non_linux_sections(self):
        markdown = (
            "### Fixes\n\n#### General\n\n- a\n\n#### 🪟 Windows\n\n- b\n\n"
            "#### 🍎 macOS\n\n- c\n\n#### 🐧 Linux\n\n- d\n\n### Thanks\n\nAll"
        )
        assert strip_non_linux_sections(markdown) == (
            "### Fixes\n\n#### General\n\n- a\n\n#### 🐧 Linux\n\n- d\n\n### Thanks\n\nAll"
        )

    def test_latest_entry_formats_as_appstream(self):
        entry = get_latest_entry(CHANGELOG_PATH.read_text(encoding="utf-8"))
        appstream = format_changelog(
            markdown_to_html(strip_non_linux_sections(entry)), "appstream"
        )
        assert "<ul>" in appstream
        assert "<li>" in appstream
        # No bytes repr leaking in from encoding the changelog before parsing
        assert appstream.split("<p>", 1)[1].strip().startswith("DisplayCAL")
