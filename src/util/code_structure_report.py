# -*- coding: utf-8 -*-

import os
import importlib
import inspect
import pkgutil
from inspect import isfunction, isclass, ismethod

import DisplayCAL


def main():
    """count the number of lines each method and function takes and report them, so we can see the progress.

    The motivation of this script was to prove that for some code paths the functions/methods are extremely long (I saw
    function more than 5000+ lines of code, this is one single function, and yes this script was to prove that it really
    exist). This is not a good approach for maintainable code.
    """
    report = {}

    path_traversal = [os.path.dirname(DisplayCAL.__file__)]
    for module_info in pkgutil.walk_packages(path_traversal):
        module_name = module_info.name
        print(module_name)
        try:
            # pkgutil.get_loader(module_info)
            module = importlib.import_module("DisplayCAL.%s" % module_info.name)
        except ModuleNotFoundError:
            continue

        all_functions = inspect.getmembers(module, isfunction)
        for func_name, func in all_functions:
            source_lines = inspect.getsourcelines(func)[0]
            source_length = len(source_lines)
            key = "%s.%s" % (module_name, func_name)
            report[key] = source_length
            print(key)

        all_classes = inspect.getmembers(module, isclass)
        for class_name, class_ in all_classes:
            methods = inspect.getmembers(class_, ismethod)
            for method_name, method in methods:
                try:
                    source_lines = inspect.getsourcelines(method)[0]
                    source_length = len(source_lines)
                    key = "%s.%s.%s" % (module_name, class_name, method_name)
                    report[key] = source_length
                    print(key)
                except TypeError:
                    pass

    print(report)


if __name__ == "__main__":
    main()
