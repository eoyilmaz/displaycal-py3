"""This module provides a JSONDict class, which extends LazyDict to create a
lazy-loading dictionary for JSON data. It allows efficient parsing and
manipulation of JSON files by loading data only when accessed.
"""
import demjson_compat

from DisplayCAL.lazydict import LazyDict


class JSONDict(LazyDict):
    """JSON lazy dictionary"""

    def parse(self, fileobj):
        dict.update(self, demjson_compat.decode(fileobj.read()))
