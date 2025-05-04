# -*- coding: utf-8 -*-

import re


def floatlist(alist):
    """Convert all list items to floats (0.0 on error)"""
    result = []
    for item in alist:
        try:
            result.append(float(item))
        except ValueError:
            result.append(0.0)
    return result


def get(alist, index, default=None):
    """Similar to dict.get, return item at index or default if not in list"""
    if -1 < index < len(alist):
        return alist[index]
    return default


def index_ignorecase(self, value, start=None, stop=None):
    """Case-insensitive version of list.index"""
    items = [(item.lower() if isinstance(item, str) else item) for item in self]
    return items.index(value, start or 0, stop or len(self))


def index_fallback_ignorecase(self, value, start=None, stop=None):
    """Return index of value in list. Prefer a case-sensitive match."""
    if value in self:
        return self.index(value, start or 0, stop or len(self))
    return index_ignorecase(self, value, start or 0, stop or len(self))


def intlist(alist):
    """Convert all list items to ints (0 on error)"""
    result = []
    for item in alist:
        try:
            result.append(int(item))
        except ValueError:
            result.append(0)
    return result


alphanumeric_re = re.compile(r"\D+|\d+")


def natsort_key_factory(ignorecase=True, n=10):
    """Create natural sort key function.

    Note that if integer parts are longer than n digits, sort order may no
    longer be entirely natural.

    """

    def natsort_key(item):
        matches = alphanumeric_re.findall(item)
        key = []
        for match in matches:
            if match.isdigit():
                match = match.rjust(n, "0")
            elif ignorecase:
                match = match.lower()
            key.append(match)
        return key

    return natsort_key


def natsort(list_in, ignorecase=True, reverse=False, n=10):
    """Sort a list which (also) contains integers naturally.

    Note that if integer parts are longer than n digits, sort order will no
    longer be entirely natural.

    """
    return sorted(list_in, key=natsort_key_factory(ignorecase, n), reverse=reverse)


def strlist(alist):
    """Convert all list items to strings"""
    return [str(item) for item in alist]
