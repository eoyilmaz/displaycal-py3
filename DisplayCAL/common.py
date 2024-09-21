import os
import sys

from DisplayCAL import colormath
from DisplayCAL.constants import defaults
from DisplayCAL.get_data_path import get_data_path


content_rgb_space = colormath.get_rgb_space("DCI P3 D65")
crx, cry = content_rgb_space[2:][0][:2]
cgx, cgy = content_rgb_space[2:][1][:2]
cbx, cby = content_rgb_space[2:][2][:2]
cwx, cwy = colormath.XYZ2xyY(*content_rgb_space[1])[:2]


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
