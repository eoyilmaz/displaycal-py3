#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
