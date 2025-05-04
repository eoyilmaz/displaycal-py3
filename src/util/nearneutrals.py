#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys


def nearneutrals(res=17, step=2):
    grid = []
    inc = 100.0 / res
    for i in range(0, res):
        for j in range(0, 3):
            v = [i * inc] * 3
            v[j] += step
            if v[j] > 100:
                break
            if v not in grid:
                grid.append(v)
            v = [i * inc + step] * 3
            v[j] -= step
            if v not in grid:
                grid.append(v)
    grid.sort()
    for line in grid:
        print("%.6f %.6f %.6f" % tuple(line))


if __name__ == "__main__":
    nearneutrals(*(int(v) for v in sys.argv[1:]))
