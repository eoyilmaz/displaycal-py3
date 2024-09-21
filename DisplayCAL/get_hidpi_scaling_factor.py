from DisplayCAL.common import get_default_dpi
from DisplayCAL.getcfg import getcfg


import os
import sys


def get_hidpi_scaling_factor():
    if sys.platform in ("darwin", "win32"):
        return 1.0  # Handled via app DPI
    else:
        # Linux
        from DisplayCAL.util_os import which

        if which("xrdb"):
            import subprocess as sp

            p = sp.Popen(
                ["xrdb", "-query"], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
            )
            # Format: 'Xft.dpi:        192'                                             # noqa: SC100
            stdout, stderr = p.communicate()
            for line in stdout.splitlines():
                line = line.decode()
                if line.startswith("Xft.dpi:"):
                    split = line.split()
                    dpi = split[-1]
                    try:
                        return float(dpi) / get_default_dpi()
                    except ValueError:
                        pass
        factor = None
        # XDG_CURRENT_DESKTOP delimiter is colon (':')                                  # noqa: SC100
        desktop = os.getenv("XDG_CURRENT_DESKTOP", "").split(":")
        if desktop[0] == "KDE":
            # Two env-vars exist: QT_SCALE_FACTOR and QT_SCREEN_SCALE_FACTORS.
            # According to documentation[1], the latter is 'mainly useful for debugging'
            # that's not how it is used by KDE though.                                  # noqa: SC100
            # Changing display scaling via KDE settings GUI only sets                   # noqa: SC100
            # QT_SCREEN_SCALE_FACTORS. We are thus currently ignoring QT_SCALE_FACTOR.
            # [1] https://doc.qt.io/qt-5/highdpi.html
            # QT_SCREEN_SCALE_FACTORS delimiter is semicolon (';')
            # Format: Mapping of XrandR display names to scale factor                   # noqa: SC100
            # e.g. 'VGA-1=1.5;VGA-2=2.0;'
            # or just list of scale factors e.g. '1.5;2.0;'                             # noqa: SC100
            screen_scale_factors = os.getenv("QT_SCREEN_SCALE_FACTORS", "").split(";")
            if screen_scale_factors:
                from DisplayCAL.wxaddons import wx

                match = False
                app = wx.GetApp()
                if app:
                    from DisplayCAL import RealDisplaySizeMM as RDSMM

                    if not RDSMM._displays:
                        RDSMM.enumerate_displays()
                    top = app.TopWindow
                    if top:
                        tmp = False
                    else:
                        # Create temp frame if no topwindow                             # noqa: SC100
                        top = wx.Frame(None)
                        # Move to main window location (and thus screen)
                        x, y = (
                            getcfg("position.x", False),
                            getcfg("position.y", False),
                        )
                        if None not in (x, y):
                            top.SetSaneGeometry(x, y)
                        tmp = True
                    # Get wx display                                                    # noqa: SC100
                    wx_display = top.GetDisplay()
                    if tmp:
                        # No longer need our temp frame
                        top.Destroy()
                    # Search for matching display based on geometry
                    pos = wx_display.Geometry[:2]
                    size = wx_display.Geometry[2:]
                    for item in screen_scale_factors:
                        if not item:
                            break
                        if "=" in item:
                            name, factor = item.split("=", 1)
                        else:
                            name, factor = None, item
                        for display in RDSMM._displays:
                            if display.get("pos") != pos or display.get("size") != size:
                                # No match
                                continue
                            if name and display.get("xrandr_name") != name:
                                # No match
                                continue
                            # Match found
                            match = True
                            break
                        if match:
                            break
                if not match:
                    # Use first one
                    factor = screen_scale_factors[0].split("=")[-1]
        if not factor and which("gsettings"):
            # GNOME
            import subprocess as sp

            p = sp.Popen(
                ["gsettings", "get", "org.gnome.desktop.interface", "scaling-factor"],
                stdin=sp.PIPE,
                stdout=sp.PIPE,
                stderr=sp.PIPE,
            )
            # Format: 'unint32 1'                                                       # noqa: SC100
            stdout, stderr = p.communicate()
            split = stdout.split()
            if split:
                factor = split[-1]
        if factor is not None:
            try:
                factor = float(factor)
            except ValueError:
                factor = None
        return factor
