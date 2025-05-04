# -*- coding: utf-8 -*-
"""
Parse commandline options.

Note that none of these are advertised, as they solely exist for testing and development
purposes.
"""

import sys

# Use only ascii? (DON'T)
ascii = "--ascii" in sys.argv[1:]

# Debug level (default: 0 = off). >= 1 prints debug messages
if "-d2" in sys.argv[1:] or "--debug=2" in sys.argv[1:]:
    debug = 2
elif (
    "-d1" in sys.argv[1:]
    or "--debug=1" in sys.argv[1:]
    or "-d" in sys.argv[1:]
    or "--debug" in sys.argv[1:]
):
    debug = 1
else:
    debug = 0

# Debug localization
debug_localization = "-dl" in sys.argv[1:] or "--debug-localization" in sys.argv[1:]

# Use alternate patch preview in the testchart editor?
tc_use_alternate_preview = (
    "-ap" in sys.argv[1:] or "--alternate-preview" in sys.argv[1:]
)

# Test some features even if they are not available normally
test = "-t" in sys.argv[1:] or "--test" in sys.argv[1:]

eecolor65 = "--ee65" in sys.argv[1:]

# Test sensor calibration
test_require_sensor_cal = (
    "-s" in sys.argv[1:] or "--test_require_sensor_cal" in sys.argv[1:]
)

# Test update functionality
test_update = "-tu" in sys.argv[1:] or "--test-update" in sys.argv[1:]

# Test SSL connection using badssl.com
test_badssl = False
for arg in sys.argv[1:]:
    if arg.startswith("--test-badssl="):
        test_badssl = arg.split("=", 1)[-1]

# Always fail download
always_fail_download = "--always-fail-download" in sys.argv[1:]

# HDR input profile generation: Test input curve clipping
test_input_curve_clipping = "--test-input-curve-clipping" in sys.argv[1:]

# Enable experimental features
experimental = "-x" in sys.argv[1:] or "--experimental" in sys.argv[1:]

# Verbosity level (default: 1). >= 1 prints some status information
if "-v4" in sys.argv[1:] or "--verbose=4" in sys.argv[1:]:
    verbose = 4
elif "-v3" in sys.argv[1:] or "--verbose=3" in sys.argv[1:]:
    verbose = 3
elif "-v2" in sys.argv[1:] or "--verbose=2" in sys.argv[1:]:
    verbose = 2
elif "-v0" in sys.argv[1:] or "--verbose=0" in sys.argv[1:]:
    verbose = 0  # Off
else:
    verbose = 1

# Use Colord GObject introspection interface (otherwise, use D-Bus)
use_colord_gi = "--use-colord-gi" in sys.argv[1:]

# Skip initial instrument/port detection on startup
force_skip_initial_instrument_detection = (
    "--force-skip-initial-instrument-detection" in sys.argv[1:]
)
