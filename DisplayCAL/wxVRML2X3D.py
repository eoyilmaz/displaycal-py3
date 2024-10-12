# -*- coding: utf-8 -*-

import os
import sys

from DisplayCAL.meta import name as appname
from DisplayCAL.util_os import launch_file, make_win32_compatible_long_path, waccess
from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL import x3dom

gui = "wx" in sys.modules

if gui:
    from DisplayCAL.worker import Worker, show_result_dialog
    from DisplayCAL.wxaddons import wx
    from DisplayCAL.wxfixes import GenBitmapButton as BitmapButton
    from DisplayCAL.wxwindows import BaseApp, BaseFrame, FileDrop

    class VRML2X3DFrame(BaseFrame):
        def __init__(self, html, embed, view, force, cache):
            BaseFrame.__init__(
                self,
                None,
                wx.ID_ANY,
                lang.getstr("vrml_to_x3d_converter"),
                style=wx.DEFAULT_FRAME_STYLE & ~(wx.MAXIMIZE_BOX | wx.RESIZE_BORDER),
                name="vrml2x3dframe",
            )
            self.SetIcons(
                config.get_icon_bundle(
                    [256, 48, 32, 16], "%s-VRML-to-X3D-converter" % appname
                )
            )
            self.Bind(wx.EVT_CLOSE, self.OnClose)
            self.cache = cache
            self.embed = embed
            self.force = force
            self.html = html
            self.worker = Worker(self)
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.SetSizer(sizer)
            panel = wx.Panel(self)
            sizer.Add(panel)
            panelsizer = wx.BoxSizer(wx.HORIZONTAL)
            panel.SetSizer(panelsizer)
            self.btn = BitmapButton(
                panel,
                wx.ID_ANY,
                config.geticon(256, "3d-primitives"),
                style=wx.NO_BORDER,
            )
            self.btn.SetToolTipString(lang.getstr("file.select"))
            self.btn.Bind(
                wx.EVT_BUTTON,
                lambda event: vrmlfile2x3dfile(
                    None,
                    html=html,
                    embed=embed,
                    view=view,
                    force=force,
                    cache=cache,
                    worker=self.worker,
                ),
            )
            self.droptarget = FileDrop(self)
            vrml_drop_handler = lambda vrmlpath: vrmlfile2x3dfile(
                vrmlpath,
                html=html,
                embed=embed,
                view=view,
                force=force,
                cache=cache,
                worker=self.worker,
            )
            self.droptarget.drophandlers = {
                ".vrml": vrml_drop_handler,
                ".vrml.gz": vrml_drop_handler,
                ".wrl": vrml_drop_handler,
                ".wrl.gz": vrml_drop_handler,
                ".wrz": vrml_drop_handler,
            }
            self.btn.SetDropTarget(self.droptarget)
            panelsizer.Add(self.btn, flag=wx.ALL, border=12)
            self.Fit()
            self.SetMinSize(self.GetSize())
            self.SetMaxSize(self.GetSize())

        def OnClose(self, event):
            # Hide first (looks nicer)
            self.Hide()
            # Need to use CallAfter to prevent hang under Windows if minimized
            wx.CallAfter(self.Destroy)

        def get_commands(self):
            return self.get_common_commands() + [
                "VRML-to-X3D-converter [filename...]",
                "load <filename...>",
            ]

        def process_data(self, data):
            if data[0] in ("VRML-to-X3D-converter", "load"):
                if self.IsIconized():
                    self.Restore()
                self.Raise()
                if len(data) > 1:
                    self.droptarget.OnDropFiles(0, 0, data[1:])
                return "ok"
            return "invalid"


def main():
    if "--help" in sys.argv[1:] or (not sys.argv[1:] and not gui):
        print("Convert VRML file to X3D")
        print("Author: Florian Hoech, licensed under the GPL version 3")
        print("Usage: %s [OPTION]... FILE..." % os.path.basename(sys.argv[0]))
        print("The output is written to FILENAME.x3d(.html)")
        print("")
        print(
            "  --embed      Embed viewer components in HTML instead of referencing them"
        )
        print("  --force      Force fresh download of viewer components")
        print(
            "  --no-cache   Don't use viewer components cache (only uses existing cache if"
        )
        print("               embedding components, can be overridden with --force)")
        if gui:
            print("  --no-gui     Don't use GUI (console mode)")
        print("  --no-html    Don't generate HTML file")
        print("  --view       View the generated file (if no GUI)")
        if not gui:
            print("  --batch      Don't pause after processing")
        print("  FILE         Filename of VRML file to convert")
        if gui:
            return
    if gui:
        config.initcfg("VRML-to-X3D-converter")
        lang.init()
        lang.update_defaults()
    cache = "--no-cache" not in sys.argv[1:]
    embed = "--embed" in sys.argv
    force = "--force" in sys.argv
    html = "--no-html" not in sys.argv[1:]
    if not gui:
        result = None
        view = "--view" in sys.argv[1:]
        for arg in sys.argv[1:]:
            if not arg.startswith("--"):
                result = vrmlfile2x3dfile(
                    str(arg),
                    html=html,
                    embed=embed,
                    view=view,
                    force=force,
                    cache=cache,
                    gui=gui,
                )
        if result is None:
            print("No filename given.")
        if (
            sys.stdout
            and hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "--batch" not in sys.argv[1:]
        ):
            input("Press RETURN to exit")
        sys.exit(int(not result))
    else:
        view = "--no-view" not in sys.argv[1:]
        app = BaseApp(0)
        app.TopWindow = VRML2X3DFrame(html, embed, view, force, cache)
        if sys.platform == "darwin":
            app.TopWindow.init_menubar()
        wx.CallLater(1, _main, app)
        app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    app.process_argv()
    app.TopWindow.Show()


def vrmlfile2x3dfile(
    vrmlpath=None,
    x3dpath=None,
    html=True,
    embed=False,
    view=False,
    force=False,
    cache=True,
    worker=None,
    gui=True,
):
    """Convert VRML to HTML. Output is written to <vrmlfilename>.x3d.html
    unless you set x3dpath to desired output path, or False to be prompted
    for an output path."""
    while not vrmlpath or not os.path.isfile(vrmlpath):
        if not gui:
            if not vrmlpath or vrmlpath.startswith("--"):
                print("No filename given.")
            else:
                print("%r is not a file." % vrmlpath)
            return False
        if not wx.GetApp():
            app = BaseApp(0)
        defaultDir, defaultFile = config.get_verified_path("last_vrml_path")
        dlg = wx.FileDialog(
            None,
            lang.getstr("file.select"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=lang.getstr("filetype.vrml")
            + "|*.vrml;*.vrml.gz;*.wrl.gz;*.wrl;*.wrz",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        dlg.Center(wx.BOTH)
        result = dlg.ShowModal()
        vrmlpath = dlg.GetPath()
        dlg.Destroy()
        if result != wx.ID_OK:
            return
        config.setcfg("last_vrml_path", vrmlpath)
        config.writecfg(module="VRML-to-X3D-converter", options=("last_vrml_path",))
    filename, ext = os.path.splitext(vrmlpath)
    if x3dpath is None:
        x3dpath = filename + ".x3d"
    if x3dpath:
        dirname = os.path.dirname(x3dpath)
    while not x3dpath or not waccess(dirname, os.W_OK):
        if not gui:
            if not x3dpath:
                print("No HTML output filename given.")
            else:
                print("%r is not writable." % dirname)
            return False
        if not wx.GetApp():
            app = BaseApp(0)
        if x3dpath:
            defaultDir, defaultFile = os.path.split(x3dpath)
        else:
            defaultFile = os.path.basename(filename) + ".x3d"
        dlg = wx.FileDialog(
            None,
            lang.getstr("error.access_denied.write", dirname),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=lang.getstr("filetype.x3d") + "|*.x3d",
            style=wx.SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        result = dlg.ShowModal()
        dlg.Destroy()
        if result != wx.ID_OK:
            return
        x3dpath = dlg.GetPath()
        dirname = os.path.dirname(x3dpath)
    vrmlpath, x3dpath = [str(path) for path in (vrmlpath, x3dpath)]
    if sys.platform == "win32":
        vrmlpath = make_win32_compatible_long_path(vrmlpath)
        x3dpath = make_win32_compatible_long_path(x3dpath)
    if html:
        finalpath = x3dpath + ".html"
        if sys.platform == "win32":
            finalpath = make_win32_compatible_long_path(finalpath)
            x3dpath = finalpath[:-5]
    else:
        finalpath = x3dpath
    if worker:
        worker.clear_cmd_output()
        worker.start(
            lambda result: (
                show_result_dialog(result, wx.GetApp().GetTopWindow())
                if isinstance(result, Exception)
                else result and view and launch_file(finalpath)
            ),
            x3dom.vrmlfile2x3dfile,
            wargs=(vrmlpath, x3dpath, html, embed, force, cache, worker),
            progress_title=lang.getstr("vrml_to_x3d_converter"),
            progress_start=1,
            resume=worker.progress_wnd and worker.progress_wnd.IsShownOnScreen(),
            fancy=False,
        )
    else:
        result = x3dom.vrmlfile2x3dfile(
            vrmlpath, x3dpath, html, embed, force, cache, None
        )
        if not isinstance(result, Exception) and result:
            if view:
                launch_file(finalpath)
        else:
            return False
    return True


if __name__ == "__main__":
    main()
