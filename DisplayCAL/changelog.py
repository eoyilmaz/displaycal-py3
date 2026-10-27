"""Read DisplayCAL's Markdown changelog and render it as simple HTML.

The changelog (``CHANGELOG.md``) and the GitHub release notes are Markdown.
Both the wx ``HtmlWindow`` and the Qt ``QTextBrowser`` update dialogs, and the
AppStream metadata generator, need HTML, so this module provides a small,
dependency-free Markdown to HTML converter covering what release notes use:
ATX headings, paragraphs, (nested) bullet and numbered lists, blockquotes,
fenced code blocks, horizontal rules, and the inline code, bold, italic and
link spans.
"""

from __future__ import annotations

import html
import re

CHANGELOG_FILENAME = "CHANGELOG.md"
"""str: The changelog file name, at the root of the source tree."""

_VERSION_HEADING_RE = re.compile(r"^## ", re.M)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_ITEM_RE = re.compile(r"^( *)([-*+]|\d+[.)])\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_ALERT_RE = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", re.I)


def get_latest_entry(markdown: str) -> None | str:
    """Return the body of the newest version section of a changelog.

    Version sections start with a level 2 heading (``## 3.10.0 - ...``).

    Args:
        markdown (str): The changelog Markdown.

    Returns:
        None | str: The section's Markdown without its heading, or None if
            the changelog has no version section.
    """
    parts = _VERSION_HEADING_RE.split(markdown)
    if len(parts) < 2:
        return None
    entry = parts[1].split("\n", 1)
    return entry[1].strip() if len(entry) > 1 else ""


def _inline(text: str) -> str:
    """Convert the inline Markdown spans of a line of text to HTML."""
    out = []
    # Code spans are taken verbatim, everything else is formatted
    for i, part in enumerate(re.split(r"(`+)(.+?)\1", text)):
        if i % 3 == 2:
            out.append(f"<code>{html.escape(part.strip())}</code>")
            continue
        if i % 3 == 1:
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s\"]+)\)", r'<a href="\2">\1</a>', part)
        part = re.sub(
            r'(?<![="\w])(https?://[^\s<)]+[^\s<).,;:!?])',
            r'<a href="\1">\1</a>',
            part,
        )
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", part)
        part = re.sub(r"(?<![\w_])_([^_\s][^_]*?)_(?![\w_])", r"<em>\1</em>", part)
        out.append(part)
    return "".join(out)


def _render_list(items: list[tuple[int, str, str]]) -> str:
    """Render ``(indent, marker, text)`` list items as (nested) HTML lists."""
    out = []
    stack: list[tuple[int, str]] = []
    for indent, marker, text in items:
        tag = "ol" if marker[0].isdigit() else "ul"
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if stack and indent == stack[-1][0]:
            if tag != stack[-1][1]:
                out.append(f"</li></{stack.pop()[1]}><{tag}>")
                stack.append((indent, tag))
            else:
                out.append("</li>")
        else:
            out.append(f"<{tag}>")
            stack.append((indent, tag))
        out.append(f"<li>{_inline(text)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def _read_fence(lines: list[str], i: int) -> tuple[str, int]:
    """Render the fenced code block starting at ``lines[i]``.

    Returns:
        tuple[str, int]: The HTML and the index of the closing fence line.
    """
    fence = _FENCE_RE.match(lines[i]).group(1)
    code = []
    i += 1
    while i < len(lines) and not lines[i].strip().startswith(fence):
        code.append(lines[i])
        i += 1
    return f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>", i


def _read_quote(lines: list[str], i: int) -> tuple[str, int]:
    """Render the blockquote starting at ``lines[i]``.

    A leading GitHub alert marker (``> [!WARNING]``) becomes a bold title.

    Returns:
        tuple[str, int]: The HTML and the index of the last quoted line.
    """
    quote = []
    while i < len(lines) and lines[i].lstrip().startswith(">"):
        quote.append(re.sub(r"^\s*> ?", "", lines[i]))
        i += 1
    alert = _ALERT_RE.match(quote[0])
    if alert:
        quote[0:1] = [f"**{alert.group(1).capitalize()}**", ""]
    return f"<blockquote>{markdown_to_html(chr(10).join(quote))}</blockquote>", i - 1


class _Blocks:
    """The HTML blocks rendered so far, plus the open paragraph or list."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.paragraph: list[str] = []
        self.list_items: list[tuple[int, str, str]] = []

    def flush_paragraph(self) -> None:
        if self.paragraph:
            self.out.append(f"<p>{_inline(' '.join(self.paragraph))}</p>")
            self.paragraph.clear()

    def flush_list(self) -> None:
        if self.list_items:
            self.out.append(_render_list(self.list_items))
            self.list_items.clear()

    def flush(self) -> None:
        self.flush_paragraph()
        self.flush_list()


def markdown_to_html(markdown: str) -> str:
    """Convert release-notes Markdown to an HTML fragment.

    Args:
        markdown (str): The Markdown text.

    Returns:
        str: The HTML fragment (no ``<html>``/``<body>`` wrapper).
    """
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks = _Blocks()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE_RE.match(line) or line.lstrip().startswith(">"):
            blocks.flush()
            reader = _read_fence if _FENCE_RE.match(line) else _read_quote
            block, i = reader(lines, i)
            blocks.out.append(block)
        elif not line.strip():
            blocks.flush()
        elif _HR_RE.match(line) and not blocks.list_items:
            blocks.flush()
            blocks.out.append("<hr />")
        elif heading := _HEADING_RE.match(line):
            blocks.flush()
            level = len(heading.group(1))
            blocks.out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif item := _LIST_ITEM_RE.match(line):
            blocks.flush_paragraph()
            blocks.list_items.append((len(item.group(1)), item.group(2), item.group(3)))
        elif blocks.list_items and line.startswith(" "):
            # Lazy continuation of the previous list item
            indent, marker, text = blocks.list_items[-1]
            blocks.list_items[-1] = (indent, marker, f"{text} {line.strip()}")
        else:
            blocks.flush_list()
            blocks.paragraph.append(line.strip())
        i += 1
    blocks.flush()
    return "\n".join(blocks.out)
