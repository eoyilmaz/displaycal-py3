from DisplayCAL.getcfg import getcfg


import math


def get_total_patches(
    white_patches=None,
    black_patches=None,
    single_channel_patches=None,
    gray_patches=None,
    multi_steps=None,
    multi_bcc_steps=None,
    fullspread_patches=None,
):
    if white_patches is None:
        white_patches = getcfg("tc_white_patches")
    if black_patches is None and getcfg("argyll.version") >= "1.6":
        black_patches = getcfg("tc_black_patches")
    if single_channel_patches is None:
        single_channel_patches = getcfg("tc_single_channel_patches")
    single_channel_patches_total = single_channel_patches * 3
    if gray_patches is None:
        gray_patches = getcfg("tc_gray_patches")
    if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
        gray_patches = 2
    if multi_steps is None:
        multi_steps = getcfg("tc_multi_steps")
    if multi_bcc_steps is None and getcfg("argyll.version") >= "1.6":
        multi_bcc_steps = getcfg("tc_multi_bcc_steps")
    if fullspread_patches is None:
        fullspread_patches = getcfg("tc_fullspread_patches")
    total_patches = 0
    if multi_steps > 1:
        multi_patches = int(math.pow(multi_steps, 3))
        if multi_bcc_steps > 1:
            multi_patches += int(math.pow(multi_bcc_steps - 1, 3))
        total_patches += multi_patches
        white_patches -= 1  # white always in multi channel patches

        multi_step = 255.0 / (multi_steps - 1)
        multi_values = []
        multi_bcc_values = []
        if multi_bcc_steps > 1:
            multi_bcc_step = multi_step
            for i in range(multi_bcc_steps):
                multi_values.append(str(multi_bcc_step * i))
            for i in range(multi_bcc_steps * 2 - 1):
                multi_bcc_values.append(str(multi_bcc_step / 2.0 * i))
        else:
            for i in range(multi_steps):
                multi_values.append(str(multi_step * i))
        if single_channel_patches > 1:
            single_channel_step = 255.0 / (single_channel_patches - 1)
            for i in range(single_channel_patches):
                if str(single_channel_step * i) in multi_values:
                    single_channel_patches_total -= 3
        if gray_patches > 1:
            gray_step = 255.0 / (gray_patches - 1)
            for i in range(gray_patches):
                if (
                    str(gray_step * i) in multi_values
                    or str(gray_step * i) in multi_bcc_values
                ):
                    gray_patches -= 1
    elif gray_patches > 1:
        white_patches -= 1  # white always in gray patches
        single_channel_patches_total -= 3  # black always in gray patches
    elif single_channel_patches_total:
        # black always only once in single channel patches
        single_channel_patches_total -= 2
    total_patches += (
        max(0, white_patches)
        + max(0, single_channel_patches_total)
        + max(0, gray_patches)
        + fullspread_patches
    )
    if black_patches:
        if gray_patches > 1 or single_channel_patches_total or multi_steps:
            black_patches -= 1  # black always in other patches
        total_patches += black_patches
    return total_patches
