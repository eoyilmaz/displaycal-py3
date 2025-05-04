#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os
import sys


pnpidcache = {}


def convert_hwdb_to_pnp_ids(hwdb_filename):
    with codecs.open(hwdb_filename, "r", "UTF-8", "replace") as hwdb:
        pnpid, name = None, None
        for line in hwdb:
            if line.strip().startswith("acpi:"):
                pnpid = line.split(":")[1][:3]
                continue
            elif line.strip().startswith("ID_VENDOR_FROM_DATABASE"):
                name = line.split("=", 1)[1].strip()
            else:
                continue
            if not pnpid or not name or pnpid in pnpidcache:
                continue
            pnpidcache[pnpid] = name
    if pnpidcache:
        with codecs.open(
            os.path.join(os.path.dirname(__file__), "..", "DisplayCAL", "pnp.ids"),
            "w",
            "UTF-8",
            "replace",
        ) as pnpids:
            for item in sorted(pnpidcache.items()):
                pnpids.write("%s\t%s\n" % item)


if __name__ == "__main__":
    convert_hwdb_to_pnp_ids(sys.argv[1])
