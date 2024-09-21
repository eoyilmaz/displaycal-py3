from DisplayCAL.constants import defaults
from DisplayCAL.get_data_path import get_data_path


import os


def get_ccxx_testchart():
    """Get the path to the default chart for CCMX/CCSS creation."""
    return get_data_path(
        os.path.join("ti1", defaults["colorimeter_correction.testchart"])
    )
