"""Argyll CMS tool names and related configurations for DisplayCAL.

It includes predefined tool names, optional tools, alternative naming
conventions, viewing conditions, intents, video encodings, and observer types.
"""

# Argyll CMS tools used by DisplayCAL
NAMES = [
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
OPTIONAL = [
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

PREFIXES_SUFFIXES = ["argyll"]

# Alternative tool names (from older Argyll CMS versions or with filename
# prefix/suffix like on some Linux distros)
ALTNAMES = {
    "txt2ti3": ["logo2cgats"],
    "icclu": ["xicclu"],
    "ccxxmake": ["ccmxmake"],
    "i1d3ccss": ["oeminst"],
    "spyd2en": ["oeminst"],
    "spyd4en": ["oeminst"],
}


def add_prefixes_suffixes(name: str, altname: str) -> None:
    """Add prefixes and suffixes to the alternative tool names.

    Args:
        name (str): The original tool name.
        altname (str): The alternative tool name.
    """
    for prefix_suffix in PREFIXES_SUFFIXES:
        ALTNAMES[name].append(f"{altname}-{prefix_suffix}")
        ALTNAMES[name].append(f"{prefix_suffix}-{altname}")


# Automatically populate the alternative tool names with prefixed/suffixed
# versions
for name in NAMES:
    if name not in ALTNAMES:
        ALTNAMES[name] = []
    _altnames = list(ALTNAMES[name])
    for altname in _altnames:
        add_prefixes_suffixes(name, altname)
    ALTNAMES[name].append(name)
    add_prefixes_suffixes(name, name)
    ALTNAMES[name].reverse()

# Viewing conditions supported by colprof (only predefined choices)
VIEWCONDS = [
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
INTENTS = ["a", "aa", "aw", "la", "lp", "ms", "p", "pa", "r", "s"]

# Video input/output encodings supported by collink (Argyll >= 1.6)
VIDEO_ENCODINGS = ["n", "t", "6", "7", "5", "2", "C", "x", "X"]

# Observers
# TODO: OBSERVERS should include 2012_2 and 2012_10.
OBSERVERS = ["1931_2", "1955_2", "1964_10", "1964_10c", "1978_2", "shaw"]
