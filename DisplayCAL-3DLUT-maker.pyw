#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DisplayCAL-3DLUT-maker.pyw.

This script is used to generate 3D LUTs for DisplayCAL. It executes the main functionality
from a separate script located in the 'scripts' directory.
"""

import os

exec(
    open(
        os.path.join(
            os.path.dirname(__file__),
            "scripts",
            os.path.splitext(os.path.basename(__file__))[0].lower(),
        )
    ).read()
)
