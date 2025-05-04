#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys


def create_cubic_grid(
    res=4, skip_grayscale=False, hires_outergamut=False, hires_inneraxis=False
):
    grid = []
    step = 100.0 / res
    for i in range(0, res + 1):
        for j in range(0, res + 1):
            for k in range(0, res + 1):
                outer = []
                inner = []
                for n in (i, j, k):
                    outer.append(n * step)
                    n = n * step + step / 2.0
                    if n > 100:
                        if not hires_outergamut:
                            continue
                        n = 100
                    inner.append(n)
                for v in (outer, inner):
                    if len(v) == 3 and (not skip_grayscale or v != [v[0]] * 3):
                        grid.append(v)
    step = 100.0 / (res * 2)
    if hires_outergamut:
        for i in range(0, res * 2 + 1):
            for j in range(0, res * 2 + 1):
                for k in range(0, res * 2 + 1):
                    outer = []
                    for n in (i, j, k):
                        if 0 in (i, j, k) and (
                            (
                                (i % 2 == 1 or j % 2 == 1 or k % 2 == 1)
                                and (
                                    (i == j == 0 or i == k == 0 or j == k == 0)
                                    or (i == res * 2 or j == res * 2 or k == res * 2)
                                )
                            )
                            or (
                                (i % 2 == 1 and j % 2 == 1)
                                or (i % 2 == 1 and k % 2 == 1)
                                or (j % 2 == 1 and k % 2 == 1)
                            )
                        ):
                            outer.append(n * step)
                    if len(outer) == 3 and (
                        not skip_grayscale or outer != [outer[0]] * 3
                    ):
                        grid.append(outer)
    step = 100.0 / (res * 4)
    if hires_inneraxis:
        for i in range(0, res * 4 - 1):
            for j in range(0, 3):
                v = [i * step] * 3
                v[j] += step * 2
                if v not in grid:
                    grid.append(v)
                v = [i * step + step * 2] * 3
                v[j] -= step * 2
                if v not in grid:
                    grid.append(v)
    grid.sort()
    return grid


if __name__ == "__main__":
    if len(sys.argv) > 1:
        skip_grayscale_ = sys.argv[2] == "1" if len(sys.argv) > 2 else False
        hires_outergamut_ = sys.argv[3] == "1" if len(sys.argv) > 3 else False
        hires_inneraxis_ = sys.argv[4] == "1" if len(sys.argv) > 4 else False
        grid = create_cubic_grid(
            int(sys.argv[1]), skip_grayscale_, hires_outergamut_, hires_inneraxis_
        )
        for v in grid:
            print(" ".join(str(n) for n in v))
    else:
        print(
            "Usage: cubicgrid.py <res> [skip grayscale 0|1 [hires_outergamut 0|1 [hires_inneraxis 0|1]]]"
        )
