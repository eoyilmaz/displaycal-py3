#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Executes the corresponding script from the `scripts` directory, dynamically determined by the lowercase basename of this file.

This bootstrapper allows for a concise, self-contained entry point while keeping the main logic separate and organized.

**Why:** This approach decouples the entry point from the implementation, facilitating easier maintenance, testing, and potential alternative implementations.
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
