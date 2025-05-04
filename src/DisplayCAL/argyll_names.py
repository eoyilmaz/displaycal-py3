# -*- coding: utf-8 -*-

# Argyll CMS tools used by DisplayCAL
names = [
    "applycal",
    "average",
    "cctiff",
    "ccxxmake",
    "dispcal",
    "dispread",
    "collink",
    "colprof",
    "dispwin",
    "fakeread",
    "iccgamut",
    "icclu",
    "xicclu",
    "spotread",
    "spyd2en",
    "spyd4en",
    "targen",
    "tiffgamut",
    "timage",
    "txt2ti3",
    "i1d3ccss",
    "viewgam",
    "oeminst",
    "profcheck",
    "spec2cie",
]

# Argyll CMS tools optionally used by DisplayCAL
optional = [
    "applycal",
    "average",
    "cctiff",
    "ccxxmake",
    "i1d3ccss",
    "oeminst",
    "spec2cie",
    "spyd2en",
    "spyd4en",
    "tiffgamut",
    "timage",
]

prefixes_suffixes = ["argyll"]

# Alternative tool names (from older Argyll CMS versions or with filename
# prefix/suffix like on some Linux distros)
altnames = {
    "txt2ti3": ["logo2cgats"],
    "icclu": ["xicclu"],
    "ccxxmake": ["ccmxmake"],
    "i1d3ccss": ["oeminst"],
    "spyd2en": ["oeminst"],
    "spyd4en": ["oeminst"],
}


def add_prefixes_suffixes(name, altname):
    for prefix_suffix in prefixes_suffixes:
        altnames[name].append(f"{altname}-{prefix_suffix}")
        altnames[name].append(f"{prefix_suffix}-{altname}")


# Automatically populate the alternative tool names with prefixed/suffixed
# versions
for name in names:
    if name not in altnames:
        altnames[name] = []
    _altnames = list(altnames[name])
    for altname in _altnames:
        add_prefixes_suffixes(name, altname)
    altnames[name].append(name)
    add_prefixes_suffixes(name, name)
    altnames[name].reverse()

# Viewing conditions supported by colprof (only predefined choices)
viewconds = [
    "pp",
    "pe",
    "pc",  # Argyll 1.1.1
    "mt",
    "mb",
    "md",
    "jm",
    "jd",
    "tv",  # Argyll 1.6
    "pcd",
    "ob",
    "cx",
]

# Intents supported by colprof
# pa = Argyll >= 1.3.3
# lp = Argyll >= 1.8.3
intents = ["a", "aa", "aw", "la", "lp", "ms", "p", "pa", "r", "s"]

# Video input/output encodings supported by collink (Argyll >= 1.6)
video_encodings = ["n", "t", "6", "7", "5", "2", "C", "x", "X"]

# Observers
observers = ["1931_2", "1955_2", "1964_10", "1964_10c", "1978_2", "shaw"]
