import sys


def get_default_dpi():
    if sys.platform == "darwin":
        return 72.0
    else:
        return 96.0
