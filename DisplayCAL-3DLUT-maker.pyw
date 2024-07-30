#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dynamically executes `DisplayCAL-3DLUT-maker.pyw` from the `scripts` directory.

**Benefits:**
- Decouples entry point from implementation, easing maintenance, testing, and alternative implementations.
- Concise, self-contained entry point with organized logic separation.
"""

import os

script_path = os.path.join(
    os.path.dirname(__file__),
    "scripts",
    os.path.splitext(os.path.basename(__file__))[0].lower() + ".py"
)

if os.path.isfile(script_path):
    with open(script_path, "r", encoding="utf-8") as file:
        exec(file.read())
else:
    raise FileNotFoundError(f"Script '{script_path}' not found.")
