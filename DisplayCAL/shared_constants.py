from DisplayCAL import colormath


content_rgb_space = colormath.get_rgb_space("DCI P3 D65")
crx, cry = content_rgb_space[2:][0][:2]
cgx, cgy = content_rgb_space[2:][1][:2]
cbx, cby = content_rgb_space[2:][2][:2]
cwx, cwy = colormath.XYZ2xyY(*content_rgb_space[1])[:2]
