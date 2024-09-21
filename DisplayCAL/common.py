import os
import sys

from DisplayCAL.constants import defaults
from DisplayCAL.get_data_path import get_data_path


def get_ccxx_testchart():
    """Get the path to the default chart for CCMX/CCSS creation."""
    return get_data_path(
        os.path.join("ti1", defaults["colorimeter_correction.testchart"])
    )


def get_default_dpi():
    if sys.platform == "darwin":
        return 72.0
    else:
        return 96.0
