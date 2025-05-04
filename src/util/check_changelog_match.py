#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL.meta import DOMAIN

tplpth = os.path.join(os.path.dirname(__file__), "..", "misc", "README.template.html")
with open(tplpth, "r") as tpl:
    readme = tpl.read()

chglog = re.search(
    r'<div id="(?:changelog|history)">' ".+?<h2>.+?</h2>" ".+?<dl>.+?</dd>",
    readme,
    re.S,
)
if chglog:
    chglog = chglog.group()
    chglog = re.sub(r'<div id="(?:changelog|history)">', "", chglog)
    chglog = re.sub(r"</?d[l|d]>", "", chglog)
    chglog = re.sub(r"<(?:h2|dt)>.+?</(?:h2|dt)>", "", chglog)
    chglog = re.sub(r"<h3>.+?</h3>", "", chglog)
if chglog:
    chglog = re.sub(
        re.compile(r"<h\d>(.+?)</h\d>", flags=re.I | re.S),
        r"<p><strong>\1</strong></p>",
        chglog,
    )
    chglog = re.sub(
        re.compile(r'href="(#[^"]+)"', flags=re.I),
        rf'href="https://{DOMAIN}/\1"',
        chglog,
    )

    print(chglog.encode(sys.stdout.encoding, "replace"))
