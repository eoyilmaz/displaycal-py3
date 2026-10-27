import os
import re
from hashlib import sha1
from pathlib import Path
from time import gmtime, strftime

from _native_build import meta


def format_changelog(changelog, fmt="appstream"):
    if fmt.lower() == "appstream":
        from xml.etree import ElementTree as ET

        # Remove changelog entries of prev versions
        changelog = re.sub(r'(?s:\s*<p id="changelog-.*$)', "", changelog)
        # AppStream: Do not assume the format is HTML. Only paragraph (p),
        # ordered list (ol) and unordered list (ul) are supported at this time.
        # + list items (li)
        allowed_tags = ["p", "ol", "ul", "li"]

        changelog = re.sub(r"\s*<dt(?:\s+[^>]*)?>.+?</dt>\n?", "", changelog)
        changelog = re.sub(r"<(h4|p)(?:\s+[^>]*)?>(.+?)</\1>", r"<p>\2</p>", changelog)
        # Remove everything between <!--more-->..<!--/more-->
        changelog = re.sub(r"(?s:<!--more-->.+?<!--/more-->)", "", changelog)
        # Remove all except allowed tags
        tags = re.findall(r"<[^/][^>]+>", changelog)

        for tag in tags:
            tagname = tag.strip("<>").split()[0]

            if tagname not in allowed_tags:
                changelog = changelog.replace(tag, "")
                changelog = changelog.replace("</" + tagname + ">", "")

        # Remove macOS and Windows specific items
        changelog = re.sub(
            r"(?is:<li>[^,:<]*(?:Mac ?OS ?X?|Windows)([^,:<]*):.*?</li>)", "", changelog
        )
        # Remove text "Linux" in item before colon (":")
        changelog = re.sub(r"(<li>[^,:<]*)\s+Linux([^,:<]*):", r"\1\2", changelog)

        # Conform to appstream-util validate-strict rules
        def truncate(matches, maxlen):
            return "%s%s%s" % (
                matches.group(1),
                # appstream-util validate counts bytes, not characters
                matches.group(2)
                .encode("UTF-8")[: maxlen - 3]
                .rstrip()
                .decode("UTF-8", "ignore")
                + "...",
                matches.group(3),
            )

        # - <p> maximum is 600 chars
        changelog = re.sub(
            r"(<p>)\s*([^<]{601,}?)\s*(</p>)",
            lambda matches: truncate(matches, 600),
            changelog,
        )
        # - <li> cannot end in '.'
        changelog = re.sub(r"([^.])\.\s*</li>", r"\1</li>", changelog)
        # - <li> maximum is 100 chars
        changelog = re.sub(
            r"(<li>)\s*([^<]{101,}?)\s*(<(?:ol|ul|/li)>)",
            lambda matches: truncate(matches, 100),
            changelog,
        )

        # Nice formatting
        changelog = re.sub(r"(?m:^\s+)", r"\t" * 4, changelog)  # Multi-line
        changelog = re.sub(r"(<li)", r"\t\1", changelog)
        changelog = re.sub(r"\s*\n\s*\n", "\n", changelog)
        # Remove line breaks
        changelog = re.sub(r"\s*\n+\s*", " ", changelog)

        # Parse into ETree
        tree = ET.fromstring(f"<root>{changelog}</root>")
    else:
        raise ValueError(f"Changelog format not supported: {fmt!r}")

    # Nice formatting
    from xml.sax.saxutils import escape

    changelog = ""
    nump = 0
    maxp = 3

    for lvl1 in tree:
        if lvl1.tag in {"p", "ol", "ul"}:
            text = lvl1.text.strip()

            if lvl1.tag == "p":
                if nump == maxp:
                    continue
                nump += 1

            changelog = f"{changelog}\t\t\t\t<{lvl1.tag}>\n"

            if text:
                changelog = f"{changelog}\t\t\t\t\t{escape(text)}\n"

            for lvl2 in lvl1:
                if lvl2.tag != "li":
                    continue
                changelog = f"{changelog}\t\t\t\t\t<li>\n\t\t\t\t\t\t{escape(lvl2.text.strip())}\n"

                for lvl3 in lvl2:
                    if lvl3.tag in {"p", "ol", "ul"}:
                        text = lvl3.text.strip()

                        if lvl3.tag == "p":
                            if nump == maxp:
                                continue
                            nump += 1

                        changelog = f"{changelog}\t\t\t\t\t\t<{lvl3.tag}>\n"

                        if text:
                            changelog = f"{changelog}\t\t\t\t\t\t\t{escape(text)}\n"

                        for lvl4 in lvl3:
                            if lvl4.tag == "li":
                                changelog = f"{changelog}\t\t\t\t\t\t\t<li>{escape(lvl4.text.strip())}</li>\n"

                        changelog = f"{changelog}\t\t\t\t\t\t</{lvl3.tag}>\n"
                changelog = f"{changelog}\t\t\t\t\t</li>\n"
            changelog = f"{changelog}\t\t\t\t</{lvl1.tag}>\n"
    changelog = changelog.rstrip()

    return changelog


def replace_placeholders(
    tmpl_path: Path, out_path: Path, lastmod_time=0, iterable=None
):
    with open(str(tmpl_path), encoding="UTF-8") as tmpl:
        tmpl_data = tmpl.read()

    if Path(tmpl_path).name.startswith("debian"):
        longdesc_backup = meta.LONG_DESCRIPTION
        meta.LONG_DESCRIPTION = "\n".join(
            [
                " " + (line if line.strip() else ".")
                for line in meta.LONG_DESCRIPTION.splitlines()
            ]
        )

    appdatadesc = (
        "\n\t\t\t"
        + meta.LONG_DESCRIPTION.replace("\n", "\n\t\t\t").replace(
            ".\n", ".\n\t\t</p>\n\t\t<p>\n"
        )
        + "\n\t\t"
    )
    mapping = {
        # e.g. Tue Jul 06 2010
        "DATE": strftime(
            "%a %b %d %Y", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        # e.g. Wed Jul 07 15:25:00 UTC 2010
        "DATETIME": strftime(
            "%a %b %d %H:%M:%S UTC %Y",
            gmtime(lastmod_time or os.stat(tmpl_path).st_mtime),
        ),
        "DEBPACKAGE": meta.NAME.lower(),
        # e.g. Wed, 07 Jul 2010 15:25:00 +0100
        "DEBDATETIME": strftime(
            "%a, %d %b %Y %H:%M:%S ",
            gmtime(lastmod_time or os.stat(tmpl_path).st_mtime),
        )
        + "+0000",
        "DOMAIN": meta.DOMAIN.lower(),
        "REVERSEDOMAIN": ".".join(reversed(meta.DOMAIN.split("."))),
        "ISODATE": strftime(
            "%Y-%m-%d", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        "ISODATETIME": strftime(
            "%Y-%m-%dT%H:%M:%S", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        )
        + "+0000",
        "ISOTIME": strftime(
            "%H:%M", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        "TIMESTAMP": str(int(lastmod_time)),
        "SUMMARY": meta.DESCRIPTION,
        "LONG_DESCRIPTION": meta.DESCRIPTION,
        "DESC": meta.LONG_DESCRIPTION,
        "APPDATADESC": f'<p>{appdatadesc}</p>\n\t\t<p xml:lang="en">{appdatadesc}</p>',
        "APPNAME": meta.NAME,
        "APPNAME_HTML": meta.NAME_HTML,
        "APPNAME_LOWER": meta.NAME.lower(),
        "APPSTREAM_ID": meta.APPSTREAM_ID,
        "AUTHOR": meta.AUTHOR,
        "AUTHOR_EMAIL": meta.AUTHOR_EMAIL,
        "MAINTAINER": meta.AUTHOR,
        "MAINTAINER_EMAIL": meta.AUTHOR_EMAIL,
        "MAINTAINER_EMAIL_SHA1": sha1(meta.AUTHOR_EMAIL.encode("utf-8")).hexdigest(),
        "PACKAGE": meta.NAME,
        "PY_MAXVERSION": ".".join(str(n) for n in meta.PY_MAXVERSION),
        "PY_MINVERSION": ".".join(str(n) for n in meta.PY_MINVERSION),
        "VERSION": meta.VERSION_STRING,
        "VERSION_SHORT": re.sub(r"(?:\.0){1,2}$", "", meta.VERSION_STRING),
        "URL": f"https://{meta.DOMAIN.lower()}/",
        # For share counts...
        "HTTPURL": f"http://{meta.DOMAIN.lower()}/",
        "WX_MINVERSION": ".".join(str(n) for n in meta.WX_MINVERSION),
        "YEAR": strftime("%Y", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)),
    }
    mapping.update(iterable or {})

    for key in mapping:
        val = mapping[key]
        tmpl_data = tmpl_data.replace(f"${{{key}}}", val)

    tmpl_data = tmpl_data.replace(
        f"{mapping['YEAR']}-{mapping['YEAR']}", mapping["YEAR"]
    )

    if Path(tmpl_path).name.startswith("debian"):
        meta.LONG_DESCRIPTION = longdesc_backup

    out_path = Path(out_path)

    if out_path.is_file():
        with open(str(out_path), encoding="UTF-8") as out:
            data = out.read()

        if data == tmpl_data:
            return
    elif not out_path.parent.is_dir():
        os.makedirs(out_path.parent)

    with open(str(out_path), "w", encoding="UTF-8") as out:
        out.write(tmpl_data)
