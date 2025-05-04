# -*- coding: utf-8 -*-
"""Temporary helper functions to ease OrderedDict removal."""


def dict_slice(obj, start=None, stop=None, step=None):
    """Slice the given dict.

    Args:
        obj (dict): The dictionary to work on.
        start (int, None): The start index.
        stop (int, None): The stop index.
        step (int, None): The step (currently not used).

    Returns:
        dict: The sliced dictionary.
    """
    all_keys = list(obj.keys())
    if start:
        if stop:
            return dict(
                zip(
                    all_keys[start:stop],
                    list(map(lambda key: obj[key], all_keys[start:stop])),
                )
            )
        else:
            return dict(
                zip(all_keys[start:], list(map(lambda key: obj[key], all_keys[start:])))
            )
    else:
        if stop:
            return dict(
                zip(all_keys[:stop], list(map(lambda key: obj[key], all_keys[:stop])))
            )
        else:
            start = 0
            stop = len(all_keys)
            return dict(
                zip(
                    all_keys[start:stop],
                    list(map(lambda key: obj[key], all_keys[start:stop])),
                )
            )


def dict_sort(obj, key=None):
    """Return a sorted dict.

    Args:
        obj (dict): The dictionary to work on.
        key (callable): A callable to generate the key.

    Returns:
        dict: The sorted dictionary.
    """
    new_dict = {}
    for k in sorted(obj, key=key):
        new_dict[k] = obj[k]
    return new_dict
