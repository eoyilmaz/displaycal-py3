"""Provides JSONDict, a lazy-loading JSON dictionary.

It allows efficient parsing and manipulation of JSON files by loading data only
when accessed.
"""

import demjson_compat

from DisplayCAL.lazydict import LazyDict


class JSONDict(LazyDict):
    """JSON lazy dictionary."""

    def parse(self, fileobj):
        """Parse the JSON data from the given file object.

        Args:
            fileobj (file-like object): A file-like object containing JSON
                data.
        """
        dict.update(self, demjson_compat.decode(fileobj.read()))
