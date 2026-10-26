"""Package/build metadata, populated from `DisplayCAL.meta` by `load()`.

Read as module attributes (`meta.NAME`, `meta.DOMAIN`, ...) rather than
imported by name, so `templates.replace_placeholders()`'s in-place
`LONG_DESCRIPTION` patching (for `debian.*` templates) is visible to every
caller without threading the value through function arguments.
"""

NAME = None
NAME_HTML = None
AUTHOR = None
AUTHOR_EMAIL = None
DESCRIPTION = None
LONG_DESCRIPTION = None
DOMAIN = None
PY_MAXVERSION = None
PY_MINVERSION = None
VERSION_STRING = None
VERSION_LIN = None
VERSION_MAC = None
VERSION_SRC = None
VERSION_TUPLE = None
VERSION_WIN = None
WX_MINVERSION = None
APPSTREAM_ID = None


def load() -> None:
    """Populate this module's attributes from `DisplayCAL.meta`."""
    global NAME, NAME_HTML, AUTHOR, AUTHOR_EMAIL, DESCRIPTION, LONG_DESCRIPTION
    global DOMAIN, PY_MAXVERSION, PY_MINVERSION
    global VERSION_STRING, VERSION_LIN, VERSION_MAC
    global VERSION_SRC, VERSION_TUPLE, VERSION_WIN
    global WX_MINVERSION, APPSTREAM_ID

    from textwrap import fill

    # Do not remove the following seemingly unused variable,
    # I know that it seems silly, but for now we need it
    from DisplayCAL.meta import (
        APPSTREAM_ID,
        AUTHOR,
        AUTHOR_EMAIL,
        DESCRIPTION,
        DOMAIN,
        LONG_DESCRIPTION,
        NAME,
        NAME_HTML,
        PY_MAXVERSION,
        PY_MINVERSION,
        VERSION_LIN,
        VERSION_MAC,
        VERSION_SRC,
        VERSION_STRING,
        VERSION_TUPLE,
        VERSION_WIN,
        WX_MINVERSION,
    )

    LONG_DESCRIPTION = fill(LONG_DESCRIPTION)
