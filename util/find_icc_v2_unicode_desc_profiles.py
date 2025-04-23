#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as iccp
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home


for p in set(iccprofiles_home + iccprofiles):
    if os.path.isdir(p):
        for f in os.listdir(p):
            try:
                profile = iccp.ICCProfile(os.path.join(p, f))
            except Exception:
                pass
            else:
                if isinstance(profile.tags.desc, iccp.TextDescriptionType):
                    if profile.tags.desc.get("Unicode") or profile.tags.desc.get(
                        "Macintosh"
                    ):
                        print(os.path.join(p, f))
                    if profile.tags.desc.get("Unicode"):
                        print(
                            "Unicode Language Code:",
                            profile.tags.desc.unicodeLanguageCode,
                        )
                        print("Unicode Description:", profile.tags.desc.Unicode)
                    if profile.tags.desc.get("Macintosh"):
                        print(
                            "Macintosh Language Code:", profile.tags.desc.macScriptCode
                        )
                        print("Macintosh Description:", profile.tags.desc.Macintosh)
                    if profile.tags.desc.get("Unicode") or profile.tags.desc.get(
                        "Macintosh"
                    ):
                        print("")
                elif not isinstance(profile.tags.desc, iccp.MultiLocalizedUnicodeType):
                    print(os.path.join(p, f))
                    print(
                        f"Warning: 'desc' is invalid type ({type(profile.tags.desc)})"
                    )
                    print("")
