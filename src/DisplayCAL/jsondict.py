# -*- coding: utf-8 -*-

import demjson_compat

from DisplayCAL.lazydict import LazyDict


class JSONDict(LazyDict):
    """JSON lazy dictionary"""

    def parse(self, fileobj):
        dict.update(self, demjson_compat.decode(fileobj.read()))
