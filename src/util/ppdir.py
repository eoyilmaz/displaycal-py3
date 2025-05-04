# -*- coding: utf-8 -*-

import sys

brackets = {dict: "{}", list: "[]", tuple: "()"}


def ppdir(obj, types=None, level=1, stream=sys.stdout, repr=repr):
    """Pretty-print object attributes"""
    if isinstance(obj, (dict, list, tuple)):
        if isinstance(obj, dict):
            class_ = dict
        elif isinstance(obj, list):
            class_ = list
        elif isinstance(obj, tuple):
            class_ = tuple
        stream.write(brackets[class_][0] + "\n")
        bag = obj
    else:
        bag = dir(obj)

    for stuff in bag:
        if isinstance(obj, dict):
            item = obj[stuff]
        elif isinstance(obj, (list, tuple)):
            item = stuff
        else:
            item = getattr(obj, stuff)
        if types:
            match = False
            for type_ in types:
                if isinstance(item, type_):
                    match = True
                    break
            if not match:
                continue
        stream.write(
            ("    " * level)
            + (((repr(stuff) if level else stuff) + ": ") if item is not stuff else "")
        )
        if isinstance(item, (str, int, float)):
            # if isinstance(item, (str, unicode)) and "\n" in item:
            # stream.write('"""' + item + '"""' + ("," if level else "") + '\n')
            # else:
            stream.write(repr(item) + ("," if level else "") + "\n")
        elif isinstance(item, (dict, list, tuple)):
            if len(("    " * level) + repr(item)) < 80:
                stream.write(repr(item) + ("," if level else "") + "\n")
            else:
                # stream.write(brackets[item.__class__][0] + '\n')
                ppdir(item, types, level=level + 1, stream=stream)
                # stream.write(("    " * level) + brackets[item.__class__][1] + ("," if level else "") + '\n')
        else:
            stream.write(repr(item) + ("," if level else "") + "\n")
    if isinstance(obj, (dict, list, tuple)):
        stream.write(
            ("    " * (level - 1))
            + brackets[class_][1]
            + ("," if level - 1 else "")
            + "\n"
        )
        bag = obj
