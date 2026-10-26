import re
from pathlib import Path

from _native_build import meta
from _native_build.templates import format_changelog, replace_placeholders


def strip_non_linux_sections(markdown: str) -> str:
    """Remove the Windows and macOS sections of a changelog entry.

    AppStream metadata is only used on Linux.
    """
    lines = []
    skip_level = None
    for line in markdown.split("\n"):
        heading = re.match(r"(#+)\s", line)
        if heading:
            level = len(heading.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and re.search(r"\b(?:Windows|macOS)\b", line):
                skip_level = level
        if skip_level is None:
            lines.append(line)
    return "\n".join(lines)


def generate(pydir: Path, lastmod_time) -> None:
    """Generate dist/<APPSTREAM_ID>.appdata.xml from misc/<APPSTREAM_ID>.appdata.xml."""
    from DisplayCAL.changelog import (
        CHANGELOG_FILENAME,
        get_latest_entry,
        markdown_to_html,
    )

    with open(str(Path(pydir, CHANGELOG_FILENAME)), encoding="UTF-8") as f:
        changelog = markdown_to_html(
            strip_non_linux_sections(get_latest_entry(f.read()) or "")
        )

    from DisplayCAL import localization as lang
    from DisplayCAL._setup import get_scripts

    scripts = get_scripts()
    provides = [f"<python3>{meta.NAME}</python3>"]

    for script, desc in scripts:
        provides.append(f"<binary>{script}</binary>")

    provides = "\n\t\t".join(provides)
    lang.init()
    languages = []

    for code, tdict in sorted(lang.LDICT.items()):
        if code == "en":
            continue

        untranslated = 0

        for key in tdict:
            if key.startswith("*") and key != "*":
                untranslated += 1

        languages.append(
            '<lang percentage="%i">%s</lang>'
            % (round((1 - untranslated / (len(tdict) - 1.0)) * 100), code)
        )

    languages = "\n\t\t".join(languages)
    tmpl_name = meta.APPSTREAM_ID + ".appdata.xml"
    misc_tmpl_name = Path(pydir, "misc", tmpl_name)
    dist_tmpl_name = Path(pydir, "dist", tmpl_name)
    replace_placeholders(
        misc_tmpl_name,
        dist_tmpl_name,
        lastmod_time,
        {
            "APPDATAPROVIDES": provides,
            "LANGUAGES": languages,
            "CHANGELOG": format_changelog(changelog, "appstream"),
        },
    )
