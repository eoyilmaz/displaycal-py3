"""Parse commandline options.

Note that none of these are advertised, as they solely exist for testing and development
purposes.
"""

import sys

# Use only ascii? (DON'T)
ASCII = "--ascii" in sys.argv[1:]

# Debug level (default: 0 = off). >= 1 prints debug messages
if "-d2" in sys.argv[1:] or "--debug=2" in sys.argv[1:]:
    DEBUG = 2
elif (
    "-d1" in sys.argv[1:]
    or "--debug=1" in sys.argv[1:]
    or "-d" in sys.argv[1:]
    or "--debug" in sys.argv[1:]
):
    DEBUG = 1
else:
    DEBUG = 0

# Debug localization
DEBUG_LOCALIZATION = "-dl" in sys.argv[1:] or "--debug-localization" in sys.argv[1:]

# Use alternate patch preview in the testchart editor?
TC_USE_ALTERNATE_PREVIEW = (
    "-ap" in sys.argv[1:] or "--alternate-preview" in sys.argv[1:]
)

# Test some features even if they are not available normally
TEST = "-t" in sys.argv[1:] or "--test" in sys.argv[1:]

EECOLOR65 = "--ee65" in sys.argv[1:]

# Test sensor calibration
TEST_REQUIRE_SENSOR_CAL = (
    "-s" in sys.argv[1:] or "--test_require_sensor_cal" in sys.argv[1:]
)

# Test update functionality
TEST_UPDATE = "-tu" in sys.argv[1:] or "--test-update" in sys.argv[1:]

# Test SSL connection using badssl.com
TEST_BADSSL = False
for arg in sys.argv[1:]:
    if arg.startswith("--test-badssl="):
        TEST_BADSSL = arg.split("=", 1)[-1]

# Always fail download
ALWAYS_FAIL_DOWNLOAD = "--always-fail-download" in sys.argv[1:]

# HDR input profile generation: Test input curve clipping
TEST_INPUT_CURVE_CLIPPING = "--test-input-curve-clipping" in sys.argv[1:]

# Enable experimental features
EXPERIMENTAL = "-x" in sys.argv[1:] or "--experimental" in sys.argv[1:]

# Verbosity level (default: 1). >= 1 prints some status information
if "-v4" in sys.argv[1:] or "--verbose=4" in sys.argv[1:]:
    VERBOSE = 4
elif "-v3" in sys.argv[1:] or "--verbose=3" in sys.argv[1:]:
    VERBOSE = 3
elif "-v2" in sys.argv[1:] or "--verbose=2" in sys.argv[1:]:
    VERBOSE = 2
elif "-v0" in sys.argv[1:] or "--verbose=0" in sys.argv[1:]:
    VERBOSE = 0  # Off
else:
    VERBOSE = 1

# Use Colord GObject introspection interface (otherwise, use D-Bus)
USE_COLORD_GI = "--use-colord-gi" in sys.argv[1:]

# Skip initial instrument/port detection on startup
FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION = (
    "--force-skip-initial-instrument-detection" in sys.argv[1:]
)
