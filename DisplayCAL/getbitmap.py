from DisplayCAL.config import bitmaps, get_default_dpi, set_default_app_dpi
from DisplayCAL.get_data_path import get_data_path
from DisplayCAL.getcfg import getcfg
from DisplayCAL.meta import name as appname


import os
import sys


def getbitmap(name, display_missing_icon=True, scale=True, use_mask=False):
    """
    Create (if necessary) and return a named bitmap.

    name has to be a relative path to a png file, omitting the extension,
    e.g. 'theme/mybitmap' or 'theme/icons/16x16/myicon',
    which is searched for in the data directories.
    If a matching file is not found, a placeholder bitmap is returned.
    The special name 'empty' will always return a transparent bitmap of the given size,
    e.g. '16x16/empty' or just 'empty' (size defaults to 16x16 if not given).
    """
    from DisplayCAL.wxaddons import wx

    if name not in bitmaps:
        parts = name.split("/")
        w = 16
        h = 16
        size = []
        if len(parts) > 1:
            size = parts[-2].split("x")
            if len(size) == 2:
                try:
                    w, h = list(map(int, size))
                except ValueError:
                    size = []
        ow, oh = w, h
        set_default_app_dpi()
        if scale:
            scale = getcfg("app.dpi") / get_default_dpi()
        else:
            scale = 1
        if scale > 1:
            # HighDPI support
            w = int(round(w * scale))
            h = int(round(h * scale))
        if parts[-1] == "empty":
            if wx.VERSION < (3,):
                use_mask = True
            if use_mask and sys.platform == "win32":
                bmp = wx.EmptyBitmap(w, h)
                bmp.SetMaskColour(wx.Colour(0, 0, 0))
            else:
                bmp = wx.EmptyBitmapRGBA(w, h, 255, 0, 255, 0)
        else:
            if parts[-1].startswith(appname):
                parts[-1] = parts[-1].lower()
            oname = parts[-1]
            if "#" in oname:
                # Hex format, RRGGBB or RRGGBBAA                                        # noqa: SC100
                oname, color = oname.split("#", 1)
                parts[-1] = oname
            else:
                color = None
            inverted = oname.endswith("-inverted")
            if inverted:
                oname = parts[-1] = oname.split("-inverted")[0]
            name2x = f"{oname}@2x"
            name4x = f"{oname}@4x"
            path = None
            for i in range(5):
                if scale > 1:
                    if len(size) == 2:
                        # Icon
                        if i == 0:
                            # HighDPI support. Try scaled size
                            parts[-2] = "%ix%i" % (w, h)
                        elif i == 1:
                            if scale < 1.75 or scale == 2:
                                continue
                            # HighDPI support. Try @4x version                          # noqa: SC100
                            parts[-2] = "%ix%i" % (ow, oh)
                            parts[-1] = name4x
                        elif i == 2:
                            # HighDPI support. Try @2x version                          # noqa: SC100
                            parts[-2] = "%ix%i" % (ow, oh)
                            parts[-1] = name2x
                        elif i == 3:
                            # HighDPI support. Try original size times two
                            parts[-2] = "%ix%i" % (ow * 2, oh * 2)
                            parts[-1] = oname
                        else:
                            # Try original size
                            parts[-2] = "%ix%i" % (ow, oh)
                    else:
                        # Theme graphic
                        if i in (0, 3):
                            continue
                        elif i == 1:
                            if scale < 1.75 or scale == 2:
                                continue
                            # HighDPI support. Try @4x version                          # noqa: SC100
                            parts[-1] = name4x
                        elif i == 2:
                            # HighDPI support. Try @2x version                          # noqa: SC100
                            parts[-1] = name2x
                        else:
                            # Try original size
                            parts[-1] = oname
                if sys.platform not in ("darwin", "win32") and parts[-1].startswith(
                    appname.lower()
                ):
                    # Search /usr/share/icons on Linux first
                    path = get_data_path(
                        "{}.png".format(os.path.join(parts[-2], "apps", parts[-1]))
                    )
                if not path:
                    path = get_data_path("{}.png".format(os.path.sep.join(parts)))
                if path or scale == 1:
                    break
            if path:
                bmp = wx.Bitmap(path)
                if not bmp.IsOk():
                    path = None
            if path:
                img = None
                if scale > 1 and i:
                    rescale = False
                    if i in (1, 2):
                        # HighDPI support. 4x/2x version, determine scaled size         # noqa: SC100
                        w, h = [int(round(v / (2 * (3 - i)) * scale)) for v in bmp.Size]
                        rescale = True
                    elif len(size) == 2:
                        # HighDPI support. Icon
                        rescale = True
                    if rescale and (bmp.Size[0] != w or bmp.Size[1] != h):
                        # HighDPI support. Rescale                                      # noqa: SC100
                        img = bmp.ConvertToImage()
                        if (
                            not hasattr(wx, "IMAGE_QUALITY_BILINEAR")
                            or oname == "list-add"
                        ):
                            # In case bilinear is not supported, and to prevent         # noqa: SC100
                            # black borders after resizing for some images
                            quality = wx.IMAGE_QUALITY_NORMAL
                        elif oname in ():
                            # Hmm. Everything else looks great with bicubic,            # noqa: SC100
                            # but this one gets jaggy unless we use bilinear            # noqa: SC100
                            quality = wx.IMAGE_QUALITY_BILINEAR
                        elif scale < 1.5 or i == 1:
                            quality = wx.IMAGE_QUALITY_BICUBIC
                        else:
                            quality = wx.IMAGE_QUALITY_BILINEAR
                        img.Rescale(w, h, quality=quality)
                factors = None
                if (
                    not inverted
                    and len(parts) > 2
                    and parts[-3] == "icons"
                    and (ow, oh) != (10, 10)
                    and oname
                    not in ("black_luminance", "check_all", "contrast", "luminance")
                    and max(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)[:3]) < 102
                ):
                    # Automatically invert B&W image if background is dark
                    # (exceptions do apply)
                    if not img:
                        img = bmp.ConvertToImage()
                    if img.IsBW():
                        inverted = True
                # Invert after resize (avoids jaggies)
                if inverted or color:
                    if not img:
                        img = bmp.ConvertToImage()
                    alpha = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT).alpha
                    if oname in [
                        "applications-system",
                        "color",
                        "document-open",
                        "document-save-as",
                        "edit-delete",
                        "image-x-generic",
                        "info",
                        "install",
                        "list-add",
                        "package-x-generic",
                        "question",
                        "rgbsquares",
                        "stock_3d-color-picker",
                        "stock_lock",
                        "stock_lock-open",
                        "stock_refresh",
                        "web",
                        "window-center",
                        "zoom-best-fit",
                        "zoom-in",
                        "zoom-original",
                        "zoom-out",
                    ]:
                        # Scale 85 to 255 and adjust alpha
                        factors = (3, 3, 3, alpha / 255.0)
                    else:
                        if inverted:
                            img.Invert()
                        if alpha != 255:
                            # Only adjust alpha
                            factors = (1, 1, 1, alpha / 255.0)
                    if factors:
                        R, G, B = factors[:3]
                        if len(factors) > 3:
                            alpha = factors[3]
                        else:
                            alpha = 1.0
                        img = img.AdjustChannels(R, G, B, alpha)
                    if color:
                        # Hex format, RRGGBB or RRGGBBAA                                # noqa: SC100
                        R = int(color[0:2], 16) / 255.0
                        G = int(color[2:4], 16) / 255.0
                        B = int(color[4:6], 16) / 255.0
                        if len(color) > 6:
                            alpha = int(color[6:8], 16) / 255.0
                        else:
                            alpha = 1.0
                        img = img.AdjustChannels(R, G, B, alpha)
                if img:
                    bmp = img.ConvertToBitmap()
                    if not bmp.IsOk():
                        path = None
            if not path:
                print("Warning: Missing bitmap '%s'" % name)
                img = wx.Image(w, h)
                img.SetMaskColour(0, 0, 0)
                img.InitAlpha()
                bmp = img.ConvertToBitmap()
                dc = wx.MemoryDC()
                dc.SelectObject(bmp)
                if display_missing_icon:
                    art = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE, size=(w, h))
                    dc.DrawBitmap(art, 0, 0, True)
                dc.SelectObject(wx.NullBitmap)
        bitmaps[name] = bmp
    return bitmaps[name]
