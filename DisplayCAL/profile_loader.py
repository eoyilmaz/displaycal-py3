# -*- coding: utf-8 -*-

"""
Set ICC profiles and load calibration curves for all configured display devices

"""

import os
import sys
import threading
import time

from DisplayCAL.meta import (
    VERSION,
    VERSION_BASE,
    name as appname,
    version,
    version_short,
)
from DisplayCAL import config
from DisplayCAL.config import appbasename, confighome, getcfg, setcfg
from DisplayCAL.options import debug, test, verbose

if sys.platform == "win32":
    import errno
    import ctypes
    import math
    import re
    import struct
    import subprocess as sp
    import traceback
    import warnings
    import winerror
    import winreg

    import pywintypes
    import win32api
    import win32event
    import win32gui
    import win32process
    import win32ts

    from DisplayCAL.colord import device_id_from_edid
    from DisplayCAL.colormath import smooth_avg
    from DisplayCAL.config import (
        autostart,
        autostart_home,
        exe,
        exedir,
        get_data_path,
        get_default_dpi,
        get_icon_bundle,
        geticon,
        iccprofiles,
        pydir,
        enc,
    )
    from DisplayCAL.debughelpers import Error, UnloggedError, handle_error
    from DisplayCAL.edid import get_edid
    from DisplayCAL.meta import DOMAIN

    from DisplayCAL.systrayicon import Menu, MenuItem, SysTrayIcon
    from DisplayCAL.util_list import natsort_key_factory
    from DisplayCAL.util_os import (
        getenvu,
        is_superuser,
        islink,
        quote_args,
        readlink,
        safe_glob,
        which,
    )
    from DisplayCAL.util_str import safe_asciize
    from DisplayCAL.util_win import (
        DISPLAY_DEVICE_ACTIVE,
        MONITORINFOF_PRIMARY,
        USE_REGISTRY,
        calibration_management_isenabled,
        enable_per_user_profiles,
        get_active_display_device,
        get_active_display_devices,
        get_display_devices,
        get_file_info,
        get_first_display_device,
        get_pids,
        get_process_filename,
        get_real_display_devices_info,
        get_windows_error,
        per_user_profiles_isenabled,
        run_as_admin,
        win_ver,
    )
    from DisplayCAL.wxaddons import CustomGridCellEvent
    from DisplayCAL.wxfixes import ThemedGenButton, set_bitmap_labels
    from DisplayCAL.wxwindows import (
        BaseApp,
        BaseFrame,
        ConfirmDialog,
        CustomCellBoolRenderer,
        CustomGrid,
        InfoDialog,
        TaskBarNotification,
        wx,
        show_result_dialog,
        get_dialogs,
    )
    from DisplayCAL import ICCProfile as ICCP
    from DisplayCAL import madvr

    if islink(exe):
        try:
            exe = readlink(exe)
        except Exception:
            pass
        else:
            exedir = os.path.dirname(exe)

    def setup_profile_loader_task(exe, exedir, pydir):
        if sys.getwindowsversion() >= (6,):
            import taskscheduler

            taskname = appname + " Profile Loader Launcher"

            try:
                ts = taskscheduler.TaskScheduler()
            except Exception as exception:
                print("Warning - could not access task scheduler:", exception)
            else:
                if (
                    "--task" not in sys.argv[1:]
                    and is_superuser()
                    and not ts.query_task(taskname)
                ):
                    # Check if our task exists, and if it does not, create it.
                    # (requires admin privileges)
                    print("Trying to create task %r..." % taskname)
                    # Note that we use a stub so the task cannot be accidentally
                    # stopped (the stub launches the actual profile loader and
                    # then immediately exits)
                    loader_args = []
                    if os.path.basename(exe).lower() in ("python.exe", "pythonw.exe"):
                        cmd = os.path.join(exedir, "pythonw.exe")
                        pyw = os.path.normpath(
                            os.path.join(pydir, "..", appname + "-apply-profiles.pyw")
                        )
                        script = get_data_path(
                            "/".join(["scripts", appname + "-apply-profiles-launcher"])
                        )
                        if os.path.exists(pyw):
                            # Running from source or 0install
                            # Check if this is a 0install implementation, in which
                            # case we want to call 0launch with the appropriate
                            # command
                            if re.match(
                                r"sha\d+(?:new)?",
                                os.path.basename(os.path.dirname(pydir)),
                            ):
                                # No stub needed as 0install-win acts as stub
                                cmd = which("0install-win.exe") or "0install-win.exe"
                                loader_args.extend(
                                    [
                                        "run",
                                        "--batch",
                                        "--no-wait",
                                        "--offline",
                                        "--command=run-apply-profiles",
                                        "--",
                                        f"http://{DOMAIN}/0install/{appname}.xml",
                                        "--task",
                                    ]
                                )
                            else:
                                # Running from source
                                loader_args.append(script)
                        else:
                            # Regular (site-packages) install
                            loader_args.append(script)
                    else:
                        # Standalone executable
                        cmd = os.path.join(
                            pydir, appname + "-apply-profiles-launcher.exe"
                        )
                    # Start at login, restart when resuming from sleep,
                    # restart daily at 04:00
                    triggers = [
                        taskscheduler.LogonTrigger(),
                        taskscheduler.ResumeFromSleepTrigger(),
                    ]
                    daily = taskscheduler.CalendarTrigger(
                        start_boundary=time.strftime("%Y-%m-%dT04:00:00"),
                        days_interval=1,
                    )
                    actions = [taskscheduler.ExecAction(cmd, loader_args)]
                    try:
                        # Create the main task
                        created = ts.create_task(
                            taskname,
                            "Open Source Developer, " "Florian Höch",
                            "This task launches the profile "
                            "loader with the applicable "
                            "privileges for logged in users",
                            multiple_instances_policy=taskscheduler.MULTIPLEINSTANCES_IGNORENEW,
                            replace_existing=True,
                            triggers=triggers,
                            actions=actions,
                        )
                        # Create the supplementary task
                        created = ts.create_task(
                            taskname + " - Daily Restart",
                            "Open Source Developer, " "Florian Höch",
                            "This task restarts the profile "
                            "loader with the applicable "
                            "privileges for logged in users",
                            multiple_instances_policy=taskscheduler.MULTIPLEINSTANCES_IGNORENEW,
                            replace_existing=True,
                            triggers=[daily],
                            actions=actions,
                        )
                    except Exception as exception:
                        if debug:
                            exception = traceback.format_exc()
                        print(
                            "Warning - Could not create task %r:" % taskname, exception
                        )
                        if ts.stdout:
                            print(str(ts.stdout, enc))
                    else:
                        print(str(ts.stdout, enc))
                        if created:
                            # Remove autostart entries, if any
                            name = appname + " Profile Loader"
                            entries = []
                            if autostart:
                                entries.append(os.path.join(autostart, name + ".lnk"))
                            if autostart_home:
                                entries.append(
                                    os.path.join(autostart_home, name + ".lnk")
                                )
                            for entry in entries:
                                if os.path.isfile(entry):
                                    print("Removing", entry)
                                    try:
                                        os.remove(entry)
                                    except EnvironmentError as exception:
                                        print(exception)
                if "Windows 10" in win_ver()[0]:
                    # Disable Windows Calibration Loader.
                    # This is absolutely REQUIRED under Win10 1903 to prevent
                    # banding and not applying calibration twice
                    ms_cal_loader = (
                        r"\Microsoft\Windows\WindowsColorSystem\Calibration Loader"
                    )
                    try:
                        ts.disable(ms_cal_loader)
                    except Exception as exception:
                        print(
                            "Warning - Could not disable task %r:" % ms_cal_loader,
                            exception,
                        )
                        if ts.stdout:
                            print(str(ts.stdout))
                    else:
                        print(str(ts.stdout))

    class DisplayIdentificationFrame(wx.Frame):
        def __init__(self, display, pos, size):
            wx.Frame.__init__(
                self,
                None,
                pos=pos,
                size=size,
                style=wx.CLIP_CHILDREN
                | wx.STAY_ON_TOP
                | wx.FRAME_NO_TASKBAR
                | wx.NO_BORDER,
                name="DisplayIdentification",
            )
            self.SetTransparent(240)
            self.Sizer = wx.BoxSizer()
            panel_outer = wx.Panel(self)
            panel_outer.BackgroundColour = "#303030"
            panel_outer.Sizer = wx.BoxSizer()
            self.Sizer.Add(panel_outer, 1, flag=wx.EXPAND)
            panel_inner = wx.Panel(panel_outer)
            panel_inner.BackgroundColour = "#0078d7"
            panel_inner.Sizer = wx.BoxSizer()
            panel_outer.Sizer.Add(
                panel_inner,
                1,
                flag=wx.ALL | wx.EXPAND,
                border=int(math.ceil(size[0] / 12.0 / 40)),
            )
            display_parts = display.split("@", 1)
            if len(display_parts) > 1:
                info = display_parts[1].split(" - ", 1)
                display_parts[1] = "@" + " ".join(info[:1])
                if info[1:]:
                    display_parts.append(" ".join(info[1:]))
            label = "\n".join(display_parts)
            text = wx.StaticText(panel_inner, -1, label, style=wx.ALIGN_CENTER)
            text.ForegroundColour = "#FFFFFF"
            font = wx.Font(
                text.Font.PointSize * size[0] / 12.0 / 16,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_LIGHT,
            )
            if not font.SetFaceName("Segoe UI Light"):
                font = text.Font
                font.PointSize *= size[0] / 12.0 / 16
                font.weight = wx.FONTWEIGHT_LIGHT
            text.Font = font
            panel_inner.Sizer.Add(text, 1, flag=wx.ALIGN_CENTER_VERTICAL)
            for element in (self, panel_outer, panel_inner, text):
                element.Bind(wx.EVT_LEFT_UP, lambda e: self.Close())
                element.Bind(wx.EVT_MIDDLE_UP, lambda e: self.Close())
                element.Bind(wx.EVT_RIGHT_UP, lambda e: self.Close())
            self.Bind(
                wx.EVT_CHAR_HOOK, lambda e: e.KeyCode == wx.WXK_ESCAPE and self.Close()
            )
            self.Layout()
            self.Show()
            self.close_timer = wx.CallLater(3000, lambda: self and self.Close())

    class FixProfileAssociationsDialog(ConfirmDialog):
        def __init__(self, pl, parent=None):
            self.pl = pl
            ConfirmDialog.__init__(
                self,
                parent,
                msg=lang.getstr("profile_loader.fix_profile_associations_warning"),
                title=pl.get_title(),
                ok=lang.getstr("profile_loader.fix_profile_associations"),
                bitmap=geticon(32, "dialog-warning"),
                wrap=128,
            )
            dlg = self
            dlg.SetIcons(
                get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )
            scale = getcfg("app.dpi") / get_default_dpi()
            if scale < 1:
                scale = 1
            list_panel = wx.Panel(dlg, -1)
            list_panel.BackgroundColour = wx.SystemSettings.GetColour(
                wx.SYS_COLOUR_3DLIGHT
            )
            list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
            list_ctrl = wx.ListCtrl(
                list_panel,
                -1,
                style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_THEME,
                name="displays2profiles",
            )
            list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
            list_ctrl.InsertColumn(0, lang.getstr("display"))
            list_ctrl.InsertColumn(1, lang.getstr("profile"))
            list_ctrl.SetColumnWidth(0, int(200 * scale))
            list_ctrl.SetColumnWidth(1, int(420 * scale))
            # Ignore item focus/selection
            list_ctrl.Bind(
                wx.EVT_LIST_ITEM_FOCUSED,
                lambda e: list_ctrl.SetItemState(
                    e.GetIndex(), 0, wx.LIST_STATE_FOCUSED
                ),
            )
            list_ctrl.Bind(
                wx.EVT_LIST_ITEM_SELECTED,
                lambda e: list_ctrl.SetItemState(
                    e.GetIndex(), 0, wx.LIST_STATE_SELECTED
                ),
            )
            self.devices2profiles_ctrl = list_ctrl
            dlg.sizer3.Insert(
                0, list_panel, 1, flag=wx.BOTTOM | wx.ALIGN_LEFT, border=12
            )
            self.update()

        def update(self, event=None):
            self.pl._set_display_profiles(dry_run=True)
            numdisp = min(len(self.pl.devices2profiles), 5)
            scale = getcfg("app.dpi") / get_default_dpi()
            if scale < 1:
                scale = 1
            hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
            size = (640 * scale, (20 * numdisp + 25 + hscroll) * scale)
            list_ctrl = self.devices2profiles_ctrl
            list_ctrl.MinSize = size
            list_ctrl.DeleteAllItems()
            for i, (display_edid, profile, desc) in enumerate(
                self.pl.devices2profiles.values()
            ):
                index = list_ctrl.InsertStringItem(i, "")
                display = display_edid[0].replace(
                    "[PRIMARY]", lang.getstr("display.primary")
                )
                list_ctrl.SetStringItem(index, 0, display)
                list_ctrl.SetStringItem(index, 1, desc)
                if not profile:
                    continue
                try:
                    profile = ICCP.ICCProfile(profile)
                except (IOError, ICCP.ICCProfileInvalidError) as exception:
                    pass
                else:
                    if isinstance(profile.tags.get("meta"), ICCP.DictType):
                        # Check if profile mapping makes sense
                        id1 = device_id_from_edid(display_edid[1], quirk=True)
                        id2 = device_id_from_edid(display_edid[1], quirk=False)
                        if profile.tags.meta.getvalue("MAPPING_device_id") not in (
                            id1,
                            id2,
                        ):
                            list_ctrl.SetItemTextColour(index, "#FF8000")
            self.sizer0.SetSizeHints(self)
            self.sizer0.Layout()
            if event and not self.IsActive():
                self.RequestUserAttention()

    class ProfileLoaderExceptionsDialog(ConfirmDialog):
        def __init__(self, exceptions, known_apps=None):
            if known_apps is None:
                known_apps = set()
            self._exceptions = {}
            self.known_apps = known_apps
            scale = getcfg("app.dpi") / config.get_default_dpi()
            if scale < 1:
                scale = 1
            ConfirmDialog.__init__(
                self,
                None,
                title=lang.getstr("exceptions"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                wrap=120,
            )

            dlg = self

            dlg.SetIcons(
                config.get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )

            dlg.delete_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("delete"))
            dlg.sizer2.Insert(0, (12, 12))
            dlg.sizer2.Insert(0, dlg.delete_btn)
            dlg.delete_btn.Bind(wx.EVT_BUTTON, dlg.delete_handler)

            dlg.browse_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("browse"))
            dlg.sizer2.Insert(0, (12, 12))
            dlg.sizer2.Insert(0, dlg.browse_btn)
            dlg.browse_btn.Bind(wx.EVT_BUTTON, dlg.browse_handler)

            dlg.add_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("add"))
            dlg.sizer2.Insert(0, (12, 12))
            dlg.sizer2.Insert(0, dlg.add_btn)
            dlg.add_btn.Bind(wx.EVT_BUTTON, dlg.browse_handler)

            if "gtk3" in wx.PlatformInfo:
                style = wx.BORDER_SIMPLE
            else:
                style = wx.BORDER_THEME
            dlg.grid = CustomGrid(dlg, -1, size=(648 * scale, 200 * scale), style=style)
            grid = dlg.grid
            grid.DisableDragRowSize()
            grid.SetCellHighlightPenWidth(0)
            grid.SetCellHighlightROPenWidth(0)
            grid.SetDefaultCellAlignment(wx.ALIGN_LEFT, wx.ALIGN_CENTER)
            grid.SetMargins(0, 0)
            grid.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
            grid.SetScrollRate(5, 5)
            grid.draw_horizontal_grid_lines = False
            grid.draw_vertical_grid_lines = False
            grid.CreateGrid(0, 4)
            grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
            font = grid.GetDefaultCellFont()
            if font.PointSize > 11:
                font.PointSize = 11
                grid.SetDefaultCellFont(font)
            grid.SetColLabelSize(int(round(self.grid.GetDefaultRowSize() * 1.4)))
            dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
            dc.SetFont(grid.GetLabelFont())
            grid.SetRowLabelSize(
                max(dc.GetTextExtent("99")[0], grid.GetDefaultRowSize())
            )
            for i in range(grid.GetNumberCols()):
                if i > 1:
                    attr = wx.grid.GridCellAttr()
                    attr.SetReadOnly(True)
                    grid.SetColAttr(i, attr)
                if i == 0:
                    # On/off checkbox
                    size = 22 * scale
                elif i == 1:
                    # Profile loader state icon
                    size = 22 * scale
                elif i == 2:
                    # Executable basename
                    size = dc.GetTextExtent("W" * 12)[0]
                else:
                    # Directory component
                    size = dc.GetTextExtent("W" * 34)[0]
                grid.SetColSize(i, size)
            for i, label in enumerate(["", "", "executable", "directory"]):
                grid.SetColLabelValue(i, lang.getstr(label))

            # On/off checkbox
            attr = wx.grid.GridCellAttr()
            renderer = CustomCellBoolRenderer()
            renderer._bitmap_unchecked = config.geticon(16, "empty")
            attr.SetRenderer(renderer)
            grid.SetColAttr(0, attr)

            # Profile loader state icon
            attr = wx.grid.GridCellAttr()
            renderer = CustomCellBoolRenderer()
            renderer._bitmap = config.geticon(16, "apply-profiles-reset")
            bitmap = renderer._bitmap
            image = bitmap.ConvertToImage().ConvertToGreyscale(0.75, 0.125, 0.125)
            renderer._bitmap_unchecked = image.ConvertToBitmap()
            attr.SetRenderer(renderer)
            grid.SetColAttr(1, attr)

            attr = wx.grid.GridCellAttr()
            attr.SetRenderer(wx.grid.GridCellStringRenderer())
            grid.SetColAttr(2, attr)

            attr = wx.grid.GridCellAttr()
            attr.SetRenderer(wx.grid.GridCellStringRenderer())
            grid.SetColAttr(3, attr)

            grid.EnableGridLines(False)

            grid.BeginBatch()
            for i, (key, (enabled, reset, path)) in enumerate(
                sorted(exceptions.items())
            ):
                grid.AppendRows(1)
                grid.SetRowLabelValue(i, "%d" % (i + 1))
                grid.SetCellValue(i, 0, "1" if enabled else "")
                grid.SetCellValue(i, 1, "1" if reset else "")
                grid.SetCellValue(i, 2, os.path.basename(path))
                grid.SetCellValue(i, 3, os.path.dirname(path))
                self._exceptions[key] = enabled, reset, path
            grid.EndBatch()

            grid.Bind(wx.EVT_KEY_DOWN, dlg.key_handler)
            grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, dlg.cell_click_handler)
            grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, dlg.cell_dclick_handler)
            grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, dlg.cell_select_handler)

            dlg.sizer3.Add(grid, 1, flag=wx.LEFT | wx.ALIGN_LEFT, border=12)

            # Legend
            sizer = wx.FlexGridSizer(2, 2, 3, 1)
            sizer.Add(wx.StaticBitmap(dlg, -1, renderer._bitmap_unchecked))
            sizer.Add(
                wx.StaticText(dlg, -1, " = " + lang.getstr("profile_loader.disable"))
            )
            sizer.Add(wx.StaticBitmap(dlg, -1, renderer._bitmap))
            sizer.Add(wx.StaticText(dlg, -1, " = " + lang.getstr("calibration.reset")))

            dlg.sizer3.Add(sizer, 1, flag=wx.LEFT | wx.TOP | wx.ALIGN_LEFT, border=12)

            dlg.buttonpanel.Layout()
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()

            # This workaround is needed to update cell colours
            grid.SelectAll()
            grid.ClearSelection()

            self.check_select_status()
            dlg.ok.Disable()

            dlg.Center()

        def _get_path(self, row):
            return os.path.join(
                self.grid.GetCellValue(row, 3), self.grid.GetCellValue(row, 2)
            )

        def _update_exception(self, row):
            path = self._get_path(row)
            enabled = int(self.grid.GetCellValue(row, 0) or 0)
            reset = int(self.grid.GetCellValue(row, 1) or 0)
            self._exceptions[path.lower()] = enabled, reset, path

        def cell_click_handler(self, event):
            if event.Col < 2:
                if self.grid.GetCellValue(event.Row, event.Col):
                    value = ""
                else:
                    value = "1"
                self.grid.SetCellValue(event.Row, event.Col, value)
                self._update_exception(event.Row)
                self.ok.Enable()
            event.Skip()

        def cell_dclick_handler(self, event):
            if event.Col > 1:
                self.browse_handler(event)
            else:
                self.cell_click_handler(event)

        def cell_select_handler(self, event):
            event.Skip()
            wx.CallAfter(self.check_select_status)

        def check_select_status(self):
            rows = self.grid.GetSelectedRows()
            self.browse_btn.Enable(len(rows) == 1)
            self.delete_btn.Enable(bool(rows))

        def key_handler(self, event):
            dlg = self
            if event.KeyCode == wx.WXK_SPACE:
                dlg.cell_click_handler(
                    CustomGridCellEvent(
                        wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
                        dlg.grid,
                        dlg.grid.GridCursorRow,
                        dlg.grid.GridCursorCol,
                    )
                )
            elif event.KeyCode in (wx.WXK_BACK, wx.WXK_DELETE):
                self.delete_handler(None)
            else:
                event.Skip()

        def browse_handler(self, event):
            if event.GetId() == self.add_btn.Id:
                lstr = "add"
                defaultDir = getenvu("ProgramW6432") or getenvu("ProgramFiles")
                defaultFile = ""
            else:
                lstr = "browse"
                row = self.grid.GetSelectedRows()[0]
                defaultDir = self.grid.GetCellValue(row, 3)
                defaultFile = self.grid.GetCellValue(row, 2)
            dlg = wx.FileDialog(
                self,
                lang.getstr(lstr),
                defaultDir=defaultDir,
                defaultFile=defaultFile,
                wildcard="*.exe",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            dlg.Center(wx.BOTH)
            result = dlg.ShowModal()
            path = dlg.GetPath()
            dlg.Destroy()
            if result == wx.ID_OK:
                if os.path.basename(path).lower() in self.known_apps:
                    show_result_dialog(
                        UnloggedError(
                            lang.getstr(
                                "profile_loader.exceptions.known_app.error",
                                os.path.basename(path),
                            )
                        )
                    )
                    return
                if event.GetId() == self.add_btn.Id:
                    # If it already exists, select the respective row
                    if path.lower() in self._exceptions:
                        for row in range(self.grid.GetNumberRows()):
                            exception = os.path.join(
                                self.grid.GetCellValue(row, 3),
                                self.grid.GetCellValue(row, 2),
                            )
                            if exception.lower() == path.lower():
                                break
                    else:
                        # Add new row
                        self.grid.AppendRows(1)
                        row = self.grid.GetNumberRows() - 1
                        self.grid.SetCellValue(row, 0, "1")
                        self.grid.SetCellValue(row, 1, "")
                        self._exceptions[path.lower()] = 1, 0, path
                self.grid.SetCellValue(row, 2, os.path.basename(path))
                self.grid.SetCellValue(row, 3, os.path.dirname(path))
                self._update_exception(row)
                self.grid.SelectRow(row)
                self.check_select_status()
                self.grid.MakeCellVisible(row, 0)
                self.ok.Enable()

        def delete_handler(self, event):
            for row in sorted(self.grid.GetSelectedRows(), reverse=True):
                del self._exceptions[self._get_path(row).lower()]
                self.grid.DeleteRows(row)
            self.check_select_status()
            self.ok.Enable()

    class ProfileAssociationsDialog(InfoDialog):
        def __init__(self, pl):
            self.monitors = []
            self.pl = pl
            self.profile_info = {}
            self.profiles = []
            self.current_user = False
            self.display_identification_frames = {}
            InfoDialog.__init__(
                self,
                None,
                msg="",
                title=lang.getstr("profile_associations"),
                ok=lang.getstr("close"),
                bitmap=geticon(32, "display"),
                show=False,
                log=False,
                wrap=128,
            )
            dlg = self
            dlg.SetIcons(
                get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )
            dlg.message.Hide()
            dlg.set_as_default_btn = wx.Button(
                dlg.buttonpanel, -1, lang.getstr("set_as_default")
            )
            dlg.sizer2.Insert(1, dlg.set_as_default_btn, flag=wx.RIGHT, border=12)
            dlg.set_as_default_btn.Bind(wx.EVT_BUTTON, dlg.set_as_default)
            dlg.set_as_default_btn.Disable()
            dlg.profile_info_btn = wx.Button(
                dlg.buttonpanel, -1, lang.getstr("profile.info")
            )
            dlg.sizer2.Insert(
                0,
                dlg.profile_info_btn,
                flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                border=12,
            )
            dlg.profile_info_btn.Bind(wx.EVT_BUTTON, dlg.show_profile_info)
            dlg.profile_info_btn.Disable()
            dlg.remove_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("remove"))
            dlg.sizer2.Insert(0, dlg.remove_btn, flag=wx.RIGHT | wx.LEFT, border=12)
            dlg.remove_btn.Bind(wx.EVT_BUTTON, dlg.remove_profile)
            dlg.remove_btn.Disable()
            dlg.add_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("add"))
            dlg.sizer2.Insert(0, dlg.add_btn, flag=wx.LEFT, border=32 + 12)
            dlg.add_btn.Bind(wx.EVT_BUTTON, dlg.add_profile)
            dlg.add_btn.Disable()
            scale = getcfg("app.dpi") / get_default_dpi()
            if scale < 1:
                scale = 1
            dlg.display_ctrl = wx.Choice(dlg, -1)
            dlg.display_ctrl.Bind(wx.EVT_CHOICE, dlg.update_profiles)
            hsizer = wx.BoxSizer(wx.HORIZONTAL)
            dlg.sizer3.Add(hsizer, 1, flag=wx.ALIGN_LEFT | wx.EXPAND | wx.TOP, border=5)
            hsizer.Add(dlg.display_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
            dlg.display_ctrl.Disable()
            dlg.identify_btn = ThemedGenButton(
                dlg, -1, lang.getstr("displays.identify")
            )
            dlg.identify_btn.MinSize = -1, dlg.display_ctrl.Size[1] + 2
            dlg.identify_btn.Bind(wx.EVT_BUTTON, dlg.identify_displays)
            hsizer.Add(
                dlg.identify_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8
            )
            dlg.identify_btn.Disable()
            if sys.getwindowsversion() >= (6,):
                hsizer = wx.BoxSizer(wx.HORIZONTAL)
                dlg.sizer3.Add(hsizer, flag=wx.ALIGN_LEFT | wx.EXPAND)
                dlg.use_my_settings_cb = wx.CheckBox(
                    dlg, -1, lang.getstr("profile_associations.use_my_settings")
                )
                dlg.use_my_settings_cb.Bind(wx.EVT_CHECKBOX, self.use_my_settings)
                hsizer.Add(
                    dlg.use_my_settings_cb,
                    flag=wx.TOP | wx.BOTTOM | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL,
                    border=12,
                )
                self.use_my_settings_cb.Disable()
                dlg.warn_bmp = wx.StaticBitmap(dlg, -1, geticon(16, "dialog-warning"))
                dlg.warning = wx.StaticText(
                    dlg,
                    -1,
                    lang.getstr(
                        "profile_associations.changing_system_defaults.warning"
                    ),
                )
                warnsizer = wx.BoxSizer(wx.HORIZONTAL)
                hsizer.Add(warnsizer, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=12)
                warnsizer.Add(dlg.warn_bmp, 0, wx.ALIGN_CENTER_VERTICAL)
                warnsizer.Add(
                    dlg.warning, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=4
                )
                self.warn_bmp.Hide()
                self.warning.Hide()
            else:
                dlg.sizer3.Add((1, 12))
            list_panel = wx.Panel(dlg, -1)
            list_panel.BackgroundColour = wx.SystemSettings.GetColour(
                wx.SYS_COLOUR_3DLIGHT
            )
            list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
            hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
            numrows = 10
            list_ctrl = wx.ListCtrl(
                list_panel,
                -1,
                size=(640 * scale, (20 * numrows + 25 + hscroll) * scale),
                style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_THEME,
                name="displays2profiles",
            )
            list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
            list_ctrl.InsertColumn(0, lang.getstr("description"))
            list_ctrl.InsertColumn(1, lang.getstr("filename"))
            list_ctrl.SetColumnWidth(0, int(430 * scale))
            list_ctrl.SetColumnWidth(1, int(210 * scale))
            list_ctrl.Bind(
                wx.EVT_LIST_ITEM_SELECTED,
                lambda e: (
                    dlg.remove_btn.Enable(),
                    dlg.set_as_default_btn.Enable(e.GetIndex() > 0),
                    dlg.profile_info_btn.Enable(),
                ),
            )
            list_ctrl.Bind(
                wx.EVT_LIST_ITEM_DESELECTED,
                lambda e: (
                    dlg.remove_btn.Disable(),
                    dlg.set_as_default_btn.Disable(),
                    dlg.profile_info_btn.Disable(),
                ),
            )
            list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, dlg.set_as_default)
            dlg.sizer3.Add(list_panel, flag=wx.BOTTOM | wx.ALIGN_LEFT, border=12)
            dlg.profiles_ctrl = list_ctrl
            dlg.fix_profile_associations_cb = wx.CheckBox(
                dlg, -1, lang.getstr("profile_loader.fix_profile_associations")
            )
            dlg.fix_profile_associations_cb.Bind(
                wx.EVT_CHECKBOX, self.toggle_fix_profile_associations
            )
            dlg.sizer3.Add(dlg.fix_profile_associations_cb, flag=wx.ALIGN_LEFT)
            dlg.disable_btns()
            dlg.update()
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            dlg.ok.SetDefault()
            dlg.update_profiles_timer = wx.Timer(dlg)
            dlg.Bind(wx.EVT_TIMER, dlg.update_profiles, dlg.update_profiles_timer)
            dlg.update_profiles_timer.Start(1000)

        def OnClose(self, event):
            InfoDialog.OnClose(self, event)

        def EndModal(self, retCode):
            self.update_profiles_timer.Stop()
            wx.Dialog.EndModal(self, retCode)

        def add_profile(self, event):
            if self.add_btn.GetAuthNeeded():
                if self.pl.elevate():
                    self.EndModal(wx.ID_CANCEL)
                return
            dlg = ConfirmDialog(
                self,
                msg=lang.getstr("profile.choose"),
                title=lang.getstr("add"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, appname + "-profile-info"),
                wrap=128,
            )
            dlg.SetIcons(
                get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )
            scale = getcfg("app.dpi") / get_default_dpi()
            if scale < 1:
                scale = 1
            list_panel = wx.Panel(dlg, -1)
            list_panel.BackgroundColour = wx.SystemSettings.GetColour(
                wx.SYS_COLOUR_3DLIGHT
            )
            list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
            hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
            numrows = 15
            list_ctrl = wx.ListCtrl(
                list_panel,
                -1,
                size=(640 * scale, (20 * numrows + 25 + hscroll) * scale),
                style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_THEME,
                name="displays2profiles",
            )
            list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
            list_ctrl.InsertColumn(0, lang.getstr("description"))
            list_ctrl.InsertColumn(1, lang.getstr("filename"))
            list_ctrl.SetColumnWidth(0, int(430 * scale))
            list_ctrl.SetColumnWidth(1, int(210 * scale))
            list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: dlg.ok.Enable())
            list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, lambda e: dlg.ok.Disable())
            list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: dlg.EndModal(wx.ID_OK))
            profiles = []
            for pth in safe_glob(os.path.join(iccprofiles[0], "*.ic[cm]")) + safe_glob(
                os.path.join(iccprofiles[0], "*.cdmp")
            ):
                try:
                    profile = ICCP.ICCProfile(pth)
                except ICCP.ICCProfileInvalidError as exception:
                    print("%s:" % pth, exception)
                    continue
                except IOError as exception:
                    print(exception)
                    continue
                if profile.profileClass == b"mntr":
                    profiles.append((profile.getDescription(), os.path.basename(pth)))
            natsort_key = natsort_key_factory()
            profiles.sort(key=lambda item: natsort_key(item[0]))
            for i, (desc, profile) in enumerate(profiles):
                pindex = list_ctrl.InsertStringItem(i, "")
                list_ctrl.SetStringItem(pindex, 0, desc)
                list_ctrl.SetStringItem(pindex, 1, profile)
            dlg.profiles_ctrl = list_ctrl
            dlg.sizer3.Add(list_panel, 1, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            dlg.ok.SetDefault()
            dlg.ok.Disable()
            dlg.Center()
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                pindex = list_ctrl.GetNextItem(
                    -1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED
                )
                if pindex > -1:
                    self.set_profile(profiles[pindex][1])
                else:
                    wx.Bell()
            dlg.Destroy()

        def identify_displays(self, event):
            for display, frame in list(self.display_identification_frames.items()):
                if not frame:
                    self.display_identification_frames.pop(display)
            for display, edid, moninfo, device in self.monitors:
                frame = self.display_identification_frames.get(display)
                if frame:
                    frame.close_timer.Stop()
                    frame.close_timer.Start(3000)
                else:
                    m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
                    m_width = abs(m_right - m_left)
                    m_height = abs(m_bottom - m_top)
                    pos = m_left + m_width / 4, m_top + m_height / 4
                    size = (m_width / 2, m_height / 2)
                    display_desc = display.replace(
                        "[PRIMARY]", lang.getstr("display.primary")
                    )
                    frame = DisplayIdentificationFrame(display_desc, pos, size)
                    self.display_identification_frames[display] = frame

        def show_profile_info(self, event):
            pindex = self.profiles_ctrl.GetNextItem(
                -1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED
            )
            if pindex < 0:
                wx.Bell()
                return
            try:
                profile = ICCP.ICCProfile(self.profiles[pindex])
            except (IOError, ICCP.ICCProfileInvalidError):
                show_result_dialog(
                    Error(
                        lang.getstr("profile.invalid") + "\n" + self.profiles[pindex]
                    ),
                    self,
                )
                return
            if profile.ID == "\0" * 16:
                id = profile.calculateID(False)
            else:
                id = profile.ID
            if id not in self.profile_info:
                # Create profile info window and store in hash table
                from wxProfileInfo import ProfileInfoFrame

                self.profile_info[id] = ProfileInfoFrame(None, -1)
                self.profile_info[id].Unbind(wx.EVT_CLOSE)
                self.profile_info[id].Bind(wx.EVT_CLOSE, self.close_profile_info)
            if (
                not self.profile_info[id].profile
                or self.profile_info[id].profile.calculateID(False) != id
            ):
                # Load profile if info window has no profile or ID is different
                self.profile_info[id].profileID = id
                self.profile_info[id].LoadProfile(profile)
            if self.profile_info[id].IsIconized():
                self.profile_info[id].Restore()
            else:
                self.profile_info[id].Show()
                self.profile_info[id].Raise()
            argyll_dir = getcfg("argyll.dir")
            if getcfg("argyll.dir") != argyll_dir:
                if self.pl.frame:
                    result = self.pl.frame.send_command(
                        None, 'set-argyll-dir "%s"' % getcfg("argyll.dir")
                    )
                else:
                    result = "ok"
                if result == "ok":
                    self.pl.writecfg()

        def close_profile_info(self, event):
            # Remove the frame from the hash table
            if self:
                self.profile_info.pop(event.GetEventObject().profileID)
            # Closes the window
            event.Skip()

        def disable_btns(self):
            self.remove_btn.Disable()
            self.profile_info_btn.Disable()
            self.set_as_default_btn.Disable()

        def remove_profile(self, event):
            if self.remove_btn.GetAuthNeeded():
                if self.pl.elevate():
                    self.EndModal(wx.ID_CANCEL)
                return
            pindex = self.profiles_ctrl.GetNextItem(
                -1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED
            )
            if pindex > -1:
                self.set_profile(self.profiles[pindex], True)
            else:
                wx.Bell()

        def set_as_default(self, event):
            if self.set_as_default_btn.GetAuthNeeded():
                if self.pl.elevate():
                    self.EndModal(wx.ID_CANCEL)
                return
            pindex = self.profiles_ctrl.GetNextItem(
                -1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED
            )
            if pindex > -1:
                self.set_profile(self.profiles[pindex])
            else:
                wx.Bell()

        def set_profile(self, profile, unset=False):
            if unset:
                fn = ICCP.unset_display_profile
            else:
                fn = ICCP.set_display_profile
            self._update_configuration(fn, profile)

        def _update_configuration(self, fn, arg0):
            dindex = self.display_ctrl.GetSelection()
            display, edid, moninfo, device = self.monitors[dindex]
            device0 = get_first_display_device(moninfo["Device"])
            if device0 and device:
                self._update_device(fn, arg0, device.DeviceKey)
                if (
                    getcfg("profile_loader.fix_profile_associations")
                    and device.DeviceKey != device0.DeviceKey
                    and self.pl._can_fix_profile_associations()
                ):
                    self._update_device(fn, arg0, device0.DeviceKey)
                self.update_profiles(True, monitor=self.monitors[dindex], next=True)
            else:
                wx.Bell()

        def _update_device(self, fn, arg0, devicekey, show_error=True):
            if (
                not USE_REGISTRY
                and fn is enable_per_user_profiles
                and not per_user_profiles_isenabled(devicekey=devicekey)
            ):
                # We need to re-associate per-user profiles to the
                # display, otherwise the associations will be lost
                # after enabling per-user if a system default profile
                # was set (but only if we call WcsSetUsePerUserProfiles
                # instead of setting the underlying registry value directly)
                monkey = devicekey.split("\\")[-2:]
                profiles = ICCP._winreg_get_display_profiles(monkey, True)
            else:
                profiles = []
            try:
                fn(arg0, devicekey=devicekey)
            except Exception as exception:
                print(
                    "%s(%r, devicekey=%r):" % (fn.__name__, arg0, devicekey), exception
                )
                if show_error:
                    wx.CallAfter(
                        show_result_dialog, UnloggedError(str(exception)), self
                    )
            for profile_name in profiles:
                ICCP.set_display_profile(profile_name, devicekey=devicekey)

        def toggle_fix_profile_associations(self, event):
            self.fix_profile_associations_cb.Value = (
                self.pl._toggle_fix_profile_associations(event, self)
            )
            if self.fix_profile_associations_cb.Value == event.IsChecked():
                self.update_profiles(True)

        def update(self, event=None):
            self.monitors = list(self.pl.monitors)
            self.display_ctrl.SetItems(
                [
                    entry[0].replace("[PRIMARY]", lang.getstr("display.primary"))
                    for entry in self.monitors
                ]
            )
            if self.monitors:
                self.display_ctrl.SetSelection(0)
            self.display_ctrl.Enable(bool(self.monitors))
            self.identify_btn.Enable(bool(self.monitors))
            self.add_btn.Enable(bool(self.monitors))
            fix = self.pl._can_fix_profile_associations()
            self.fix_profile_associations_cb.Enable(fix)
            if fix:
                self.fix_profile_associations_cb.SetValue(
                    bool(getcfg("profile_loader.fix_profile_associations"))
                )
            self.update_profiles(event)
            if event and not self.IsActive():
                self.RequestUserAttention()

        def update_profiles(self, event=None, monitor=None, next=False):
            if not monitor:
                dindex = self.display_ctrl.GetSelection()
                if -1 < dindex < len(self.monitors):
                    monitor = self.monitors[dindex]
                else:
                    if event and not isinstance(event, wx.TimerEvent):
                        wx.Bell()
                    return
            display, edid, moninfo, device = monitor
            if not device:
                if event and not isinstance(event, wx.TimerEvent):
                    wx.Bell()
                return
            if sys.getwindowsversion() >= (6,):
                current_user = per_user_profiles_isenabled(devicekey=device.DeviceKey)
                scope_changed = current_user != self.current_user
                if scope_changed:
                    self.current_user = current_user
                    self.use_my_settings_cb.SetValue(current_user)
                self.use_my_settings_cb.Enable()
                superuser = is_superuser()
                warn = not current_user and superuser
                update_layout = warn is not self.warning.IsShown()
                if update_layout:
                    self.warn_bmp.Show(warn)
                    self.warning.Show(warn)
                    self.sizer3.Layout()
                auth_needed = not (current_user or superuser)
                update_layout = self.add_btn.GetAuthNeeded() is not auth_needed
                if update_layout:
                    self.buttonpanel.Freeze()
                    self.add_btn.SetAuthNeeded(auth_needed)
                    self.remove_btn.SetAuthNeeded(auth_needed)
                    self.set_as_default_btn.SetAuthNeeded(auth_needed)
                    self.buttonpanel.Layout()
                    self.buttonpanel.Thaw()
            else:
                current_user = False
                scope_changed = False
            monkey = device.DeviceKey.split("\\")[-2:]
            profiles = ICCP._winreg_get_display_profiles(monkey, current_user)
            profiles.reverse()
            profiles_changed = profiles != self.profiles
            if profiles_changed:
                self.profiles_ctrl.Freeze()
                self.profiles = profiles
                self.disable_btns()
                self.profiles_ctrl.DeleteAllItems()
                for i, profile in enumerate(self.profiles):
                    pindex = self.profiles_ctrl.InsertStringItem(i, "")
                    description = get_profile_desc(profile, False)
                    if not i:
                        # First profile is always default
                        description += " (%s)" % lang.getstr("default")
                    self.profiles_ctrl.SetStringItem(pindex, 0, description)
                    self.profiles_ctrl.SetStringItem(pindex, 1, profile)
                self.profiles_ctrl.Thaw()
            if scope_changed or profiles_changed:
                if next or isinstance(event, wx.TimerEvent):
                    wx.CallAfter(self._next)

        def _next(self):
            locked = self.pl.lock.locked()
            if locked:
                print("ProfileAssociationsDialog: Waiting to acquire lock...")
            with self.pl.lock:
                if locked:
                    print("ProfileAssociationsDialog: Acquired lock")
                self.pl._next = True
                if locked:
                    print("ProfileAssociationsDialog: Releasing lock")

        def use_my_settings(self, event):
            self._update_configuration(enable_per_user_profiles, event.IsChecked())


class ProfileLoader(object):
    def __init__(self):
        from DisplayCAL.wxwindows import BaseApp, wx

        if not wx.GetApp():
            app = BaseApp(0, clearSigInt=sys.platform != "win32")
            BaseApp.register_exitfunc(self.shutdown)
        else:
            app = None
        self.reload_count = 0
        self.lock = threading.Lock()
        self._is_other_running_lock = threading.Lock()
        self.monitoring = True
        self._active_displays = []
        self._display_changed_event = False
        self.monitors = []  # Display devices that can be represented as ON
        self.display_devices = {}  # All display devices
        self.child_devices_count = {}
        self._current_display_key = -1
        self.numwindows = 0
        self.profile_associations = {}
        self.profiles = {}
        self.devices2profiles = {}
        self.ramps = {}
        self.linear_vcgt_values = ([], [], [])
        for j in range(3):
            for k in range(256):
                self.linear_vcgt_values[j].append([float(k), k * 257])
        self.setgammaramp_success = {}
        self.use_madhcnet = bool(config.getcfg("profile_loader.use_madhcnet"))
        self._has_display_changed = False
        self._last_exception_args = ()
        self._shutdown = False
        self._skip = "--skip" in sys.argv[1:]
        apply_profiles = bool(
            "--force" in sys.argv[1:] or config.getcfg("profile.load_on_login")
        )
        self._manual_restore = apply_profiles
        self._reset_gamma_ramps = bool(
            config.getcfg("profile_loader.reset_gamma_ramps")
        )
        self._known_apps = set(
            [
                known_app.lower()
                for known_app in config.defaults["profile_loader.known_apps"].split(";")
                + config.getcfg("profile_loader.known_apps").split(";")
            ]
        )
        self._known_window_classes = set(
            config.defaults["profile_loader.known_window_classes"].split(";")
            + config.getcfg("profile_loader.known_window_classes").split(";")
        )
        self._buggy_video_drivers = set(
            buggy_video_driver.lower()
            for buggy_video_driver in config.getcfg(
                "profile_loader.buggy_video_drivers"
            ).split(";")
        )
        self._set_exceptions()
        self._madvr_instances = []
        self._madvr_reset_cal = {}
        self._quantize = 2 ** getcfg("profile_loader.quantize_bits") - 1.0
        self._timestamp = time.time()
        self._component_name = None
        self._app_detection_msg = None
        self._hwnds_pids = set()
        self._fixed_profile_associations = set()
        self.__other_component = None, None, 0
        self.__apply_profiles = None
        if (
            sys.platform == "win32"
            and "--force" not in sys.argv[1:]
            and sys.getwindowsversion() >= (6, 1)
        ):
            if calibration_management_isenabled():
                # Incase calibration loading is handled by Windows 7 and
                # isn't forced
                self._manual_restore = False
        if (
            sys.platform != "win32"
            and apply_profiles
            and not self._skip
            and not self._is_displaycal_running()
            and not self._is_other_running(True)
        ):
            self.apply_profiles_and_warn_on_error()
        if sys.platform == "win32":
            # We create a TSR tray program only under Windows.
            # Linux has colord/Oyranos and respective session daemons should
            # take care of calibration loading

            self._pid = os.getpid()
            self._tid = threading.currentThread().ident

            class PLFrame(BaseFrame):
                def __init__(self, pl):
                    BaseFrame.__init__(self, None)
                    self.pl = pl
                    self.Bind(wx.EVT_CLOSE, pl.exit)
                    self.Bind(wx.EVT_DISPLAY_CHANGED, self.pl._display_changed)

                def get_commands(self):
                    return self.get_common_commands() + [
                        "apply-profiles [force | display-changed]",
                        "notify <message> [silent] [sticky]",
                        "reset-vcgt [force]",
                        "setlanguage <languagecode>",
                    ]

                def process_data(self, data):
                    if data[0] in ("apply-profiles", "reset-vcgt") and (
                        len(data) == 1
                        or (len(data) == 2 and data[1] in ("force", "display-changed"))
                    ):
                        if (
                            not ("--force" in sys.argv[1:] or len(data) == 2)
                            and calibration_management_isenabled()
                        ):
                            return lang.getstr("calibration.load.handled_by_os")
                        if (
                            len(data) == 1 and self.pl._is_displaycal_running()
                        ) or self.pl._is_other_running(False):
                            return "forbidden"
                        elif data[-1] == "display-changed":
                            if self.pl.lock.locked():
                                print(
                                    "PLFrame.process_data: Waiting to acquire lock..."
                                )
                            with self.pl.lock:
                                print("PLFrame.process_data: Acquired lock")
                                if self.pl._has_display_changed:
                                    # Normally calibration loading is disabled while
                                    # DisplayCAL is running. Override this when the
                                    # display has changed
                                    self.pl._manual_restore = (
                                        getcfg("profile.load_on_login") and 2
                                    )
                                print("PLFrame.process_data: Releasing lock")
                        else:
                            if data[0] == "reset-vcgt":
                                self.pl._set_reset_gamma_ramps(None, len(data))
                            else:
                                self.pl._set_manual_restore(None, len(data))
                        return "ok"
                    elif data[0] == "notify" and (
                        len(data) == 2
                        or (len(data) == 3 and data[2] in ("silent", "sticky"))
                        or (
                            len(data) == 4
                            and "silent" in data[2:]
                            and "sticky" in data[2:]
                        )
                    ):
                        self.pl.notify(
                            [data[1]],
                            [],
                            sticky="sticky" in data[2:],
                            show_notification="silent" not in data[2:],
                        )
                        return "ok"
                    elif data[0] == "setlanguage" and len(data) == 2:
                        config.setcfg("lang", data[1])
                        wx.CallAfter(self.pl.taskbar_icon.set_visual_state)
                        self.pl.writecfg()
                        return "ok"
                    return "invalid"

            class TaskBarIcon(SysTrayIcon):
                def __init__(self, pl):
                    super(TaskBarIcon, self).__init__()
                    self.pl = pl
                    self.balloon_text = None
                    self.flags = 0
                    self.set_icons()
                    self._active_icon_reset = config.get_bitmap_as_icon(
                        16, "apply-profiles-reset"
                    )
                    self._error_icon = config.get_bitmap_as_icon(
                        16, "apply-profiles-error"
                    )
                    self._animate = False
                    self.set_visual_state(True)
                    self.Bind(wx.EVT_TASKBAR_LEFT_UP, self.on_left_up)
                    self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
                    self._dclick = False
                    self._show_notification_later = None

                @property
                def _active_icon(self):
                    if debug > 1:
                        print("[DEBUG] _active_icon[%i]" % self._icon_index)
                    icon = self._active_icons[self._icon_index]
                    return icon

                @_active_icon.setter
                def _active_icon(self, icon):
                    self._active_icons.append(icon)

                def CreatePopupMenu(self):
                    # Popup menu appears on right-click
                    menu = Menu()

                    if self.pl._is_displaycal_running() or self.pl._is_other_running(
                        False
                    ):
                        restore_auto = restore_manual = reset = None
                    else:
                        restore_manual = self.pl._set_manual_restore
                        if (
                            "--force" in sys.argv[1:]
                            or calibration_management_isenabled()
                        ):
                            restore_auto = None
                        else:
                            restore_auto = self.set_auto_restore
                        reset = self.pl._set_reset_gamma_ramps
                    if (
                        "--force" not in sys.argv[1:]
                        and calibration_management_isenabled()
                    ):
                        restore_auto_kind = apply_kind = wx.ITEM_NORMAL
                    else:
                        if config.getcfg("profile.load_on_login"):
                            apply_kind = wx.ITEM_RADIO
                        else:
                            apply_kind = wx.ITEM_NORMAL
                        restore_auto_kind = wx.ITEM_CHECK

                    fix = self.pl._can_fix_profile_associations()
                    if fix:
                        fix = self.pl._toggle_fix_profile_associations

                    menu_items = [
                        (
                            "calibration.load_from_display_profiles",
                            restore_manual,
                            apply_kind,
                            "reset_gamma_ramps",
                            lambda v: not v,
                        ),
                        (
                            "calibration.reset",
                            reset,
                            apply_kind,
                            "reset_gamma_ramps",
                            None,
                        ),
                        ("-", None, False, None, None),
                        (
                            "calibration.preserve",
                            restore_auto,
                            restore_auto_kind,
                            "profile.load_on_login",
                            None,
                        ),
                        (
                            "profile_loader.fix_profile_associations",
                            fix,
                            wx.ITEM_CHECK,
                            "profile_loader.fix_profile_associations",
                            None,
                        ),
                        (
                            "show_notifications",
                            lambda event: setcfg(
                                "profile_loader.show_notifications",
                                int(event.IsChecked()),
                            ),
                            wx.ITEM_CHECK,
                            "profile_loader.show_notifications",
                            None,
                        ),
                        (
                            "tray_icon_animation",
                            self.set_animation,
                            wx.ITEM_CHECK,
                            "profile_loader.tray_icon_animation_quality",
                            None,
                        ),
                        ("-", None, False, None, None),
                        (
                            "bitdepth",
                            (
                                ("8", lambda event: self.set_bitdepth(event, 8)),
                                ("10", lambda event: self.set_bitdepth(event, 10)),
                                ("12", lambda event: self.set_bitdepth(event, 12)),
                                ("14", lambda event: self.set_bitdepth(event, 14)),
                                ("16", lambda event: self.set_bitdepth(event, 16)),
                            ),
                            wx.ITEM_CHECK,
                            "profile_loader.quantize_bits",
                            lambda v: {8: 0, 10: 1, 12: 2, 14: 3, 16: 4}[v],
                        ),
                        ("-", None, False, None, None),
                        ("exceptions", self.set_exceptions, wx.ITEM_NORMAL, None, None),
                        ("-", None, False, None, None),
                    ]
                    menu_items.append(
                        (
                            "profile_associations",
                            self.pl._set_profile_associations,
                            wx.ITEM_NORMAL,
                            None,
                            None,
                        )
                    )
                    if sys.getwindowsversion() >= (6,):
                        menu_items.append(
                            (
                                "mswin.open_display_settings",
                                self.open_display_settings,
                                wx.ITEM_NORMAL,
                                None,
                                None,
                            )
                        )
                    menu_items.append(("-", None, False, None, None))
                    menu_items.append(
                        ("menuitem.quit", self.pl.exit, wx.ITEM_NORMAL, None, None)
                    )
                    for (label, method, kind, option, oxform) in menu_items:
                        if label == "-":
                            menu.AppendSeparator()
                        else:
                            label = lang.getstr(label)
                            if option == "profile.load_on_login":
                                lstr = lang.getstr("profile.load_on_login")
                                if lang.getcode() != "de":
                                    label = label[0].lower() + label[1:]
                                label = lstr + " && " + label
                            item = MenuItem(menu, -1, label, kind=kind)
                            if not oxform:
                                oxform = bool
                            if not method:
                                item.Enable(False)
                            elif isinstance(method, tuple):
                                submenu = Menu()
                                for i, (sublabel, submethod) in enumerate(method):
                                    subitem = MenuItem(
                                        submenu, -1, lang.getstr(sublabel), kind=kind
                                    )
                                    if oxform(getcfg(option)) == i:
                                        subitem.Check(True)
                                    submenu.AppendItem(subitem)
                                    submenu.Bind(wx.EVT_MENU, submethod, id=subitem.Id)
                                menu.AppendSubMenu(submenu, label)
                                continue
                            else:
                                menu.Bind(wx.EVT_MENU, method, id=item.Id)
                            menu.AppendItem(item)
                            if kind != wx.ITEM_NORMAL:
                                if (
                                    option == "profile.load_on_login"
                                    and "--force" in sys.argv[1:]
                                ):
                                    item.Check(True)
                                else:
                                    if option == "reset_gamma_ramps":
                                        value = self.pl._reset_gamma_ramps
                                    else:
                                        value = config.getcfg(option)
                                    item.Check(method and oxform(value))

                    return menu

                def PopupMenu(self, menu):
                    if not self.check_user_attention():
                        if self.menu and self.menu is not menu:
                            self.menu.Destroy()
                        SysTrayIcon.PopupMenu(self, menu)

                def animate(self, enumerate_windows_and_processes=False, idle=False):
                    if not self.pl.monitoring:
                        return
                    if debug > 1:
                        print(
                            "[DEBUG] animate(enumerate_windows_and_processes=%s, idle=%s)"
                            % (enumerate_windows_and_processes, idle)
                        )
                    if self._icon_index < len(self._active_icons) - 1:
                        self._animate = True
                        self._icon_index += 1
                    else:
                        self._animate = False
                        self._icon_index = 0
                    self.set_visual_state(enumerate_windows_and_processes, idle)
                    if self._icon_index > 0:
                        wx.CallLater(
                            int(200 / len(self._active_icons)),
                            lambda enumerate_windows_and_processes, idle: self
                            and self.animate(enumerate_windows_and_processes, idle),
                            enumerate_windows_and_processes,
                            idle,
                        )
                    if debug > 1:
                        print("[DEBUG] /animate")

                def get_icon(self, enumerate_windows_and_processes=False, idle=False):
                    if debug > 1:
                        print(
                            "[DEBUG] get_icon(enumerate_windows_and_processes=%s, idle=%s)"
                            % (enumerate_windows_and_processes, idle)
                        )
                    if (
                        self.pl._should_apply_profiles(
                            enumerate_windows_and_processes, manual_override=None
                        )
                        or self._animate
                    ):
                        count = len(self.pl.monitors)
                        if (
                            len(
                                [
                                    i_success
                                    for i_success in sorted(
                                        self.pl.setgammaramp_success.items()
                                    )[: count or 1]
                                    if not i_success[1]
                                ]
                            )
                            != 0
                        ):
                            icon = self._error_icon
                        elif self.pl._reset_gamma_ramps:
                            icon = self._active_icon_reset
                        else:
                            if idle:
                                icon = self._idle_icon
                            else:
                                icon = self._active_icon
                    else:
                        icon = self._inactive_icon
                    if debug > 1:
                        print("[DEBUG] /get_icon")
                    return icon

                def on_left_up(self, event):
                    if self._dclick:
                        self._dclick = False
                        return
                    if not getattr(self, "_notification", None):
                        # Make sure the displayed info is up-to-date
                        locked = self.pl.lock.locked()
                        if locked:
                            print(
                                "TaskBarIcon.on_left_down: Waiting to acquire lock..."
                            )
                        with self.pl.lock:
                            if locked:
                                print("TaskBarIcon.on_left_down: Acquired lock")
                            self.pl._next = True
                            if locked:
                                print("TaskBarIcon.on_left_down: Releasing lock")
                        time.sleep(0.11)
                        locked = self.pl.lock.locked()
                        if locked:
                            print(
                                "TaskBarIcon.on_left_down: Waiting to acquire lock..."
                            )
                        with self.pl.lock:
                            if locked:
                                print("TaskBarIcon.on_left_down: Acquired lock")
                            pass
                            if locked:
                                print("TaskBarIcon.on_left_down: Releasing lock")
                        self._show_notification_later = wx.CallLater(
                            40, self.show_notification
                        )
                    else:
                        self.show_notification(toggle=True)

                def on_left_dclick(self, event):
                    self._dclick = True
                    if not self.pl._is_other_running(False):
                        if (
                            self._show_notification_later
                            and self._show_notification_later.IsRunning()
                        ):
                            self._show_notification_later.Stop()
                        locked = self.pl.lock.locked()
                        if locked:
                            print(
                                "TaskBarIcon.on_left_dclick: Waiting to acquire lock..."
                            )
                        with self.pl.lock:
                            if locked:
                                print("TaskBarIcon.on_left_dclick: Acquired lock")
                            self.pl._manual_restore = True
                            self.pl._next = True
                            if locked:
                                print("TaskBarIcon.on_left_dclick: Releasing lock")

                def check_user_attention(self):
                    dlgs = get_dialogs()
                    if dlgs:
                        wx.Bell()
                        for dlg in dlgs:
                            # Need to request user attention for all open
                            # dialogs because calling it only on the topmost
                            # one does not guarantee taskbar flash
                            dlg.RequestUserAttention()
                        dlg.Raise()
                        return dlg

                def open_display_settings(self, event):
                    print("Menu command: Open display settings")
                    try:
                        sp.call(
                            [
                                "control",
                                "/name",
                                "Microsoft.Display",
                                "/page",
                                "Settings",
                            ],
                            close_fds=True,
                        )
                    except Exception as exception:
                        wx.Bell()
                        print(exception)

                def set_animation(self, event=None):
                    q = getcfg("profile_loader.tray_icon_animation_quality")
                    if q:
                        q = 0
                    else:
                        q = 2
                    print("Menu command: Set tray icon animation", q)
                    setcfg("profile_loader.tray_icon_animation_quality", q)
                    self.set_icons()

                def set_auto_restore(self, event):
                    print("Menu command: Preserve calibration state", event.IsChecked())
                    config.setcfg("profile.load_on_login", int(event.IsChecked()))
                    self.pl.writecfg()
                    if event.IsChecked():
                        if self.pl.lock.locked():
                            print("TaskBarIcon: Waiting to acquire lock...")
                        with self.pl.lock:
                            print("TaskBarIcon: Acquired lock")
                            self.pl._manual_restore = True
                            self.pl._next = True
                            print("TaskBarIcon: Releasing lock")
                    else:
                        self.set_visual_state()

                def set_bitdepth(self, event=None, bits=16):
                    print("Menu command: Set quantization bitdepth", bits)
                    setcfg("profile_loader.quantize_bits", bits)
                    with self.pl.lock:
                        self.pl._quantize = 2**bits - 1.0
                        self.pl.ramps = {}
                        self.pl._manual_restore = True

                def set_exceptions(self, event):
                    print("Menu command: Set exceptions")
                    dlg = ProfileLoaderExceptionsDialog(
                        self.pl._exceptions, self.pl._known_apps
                    )
                    result = dlg.ShowModal()
                    if result == wx.ID_OK:
                        exceptions = []
                        for key in dlg._exceptions:
                            enabled, reset, path = dlg._exceptions[key]
                            exceptions.append("%i:%i:%s" % (enabled, reset, path))
                            print(
                                "Enabled=%s" % bool(enabled),
                                "Action=%s" % (reset and "Reset" or "Disable"),
                                path,
                            )
                        if not exceptions:
                            print("Clearing exceptions")
                        config.setcfg("profile_loader.exceptions", ";".join(exceptions))
                        self.pl._exceptions = dlg._exceptions
                        self.pl._exception_names = set(
                            os.path.basename(key) for key in dlg._exceptions
                        )
                        self.pl.writecfg()
                    else:
                        print("Cancelled setting exceptions")
                    dlg.Destroy()

                def set_icons(self):
                    bitmap = config.geticon(16, "apply-profiles-tray")
                    image = bitmap.ConvertToImage()
                    # Use Rec. 709 luma coefficients to convert to grayscale
                    bitmap = image.ConvertToGreyscale(
                        0.2126, 0.7152, 0.0722
                    ).ConvertToBitmap()
                    icon = wx.IconFromBitmap(bitmap)
                    self._active_icons = []
                    self._icon_index = 0
                    anim_quality = getcfg("profile_loader.tray_icon_animation_quality")
                    if anim_quality == 2:
                        numframes = 8
                    elif anim_quality == 1:
                        numframes = 4
                    else:
                        numframes = 1
                    for i in range(numframes):
                        if i:
                            rad = i / float(numframes)
                            bitmap = config.geticon(
                                16, "apply-profiles-tray-%i" % (360 * rad)
                            )
                            image = bitmap.ConvertToImage()
                            image.RotateHue(-rad)
                        self._active_icon = wx.IconFromBitmap(image.ConvertToBitmap())
                    self._idle_icon = self._active_icon
                    self._inactive_icon = icon

                def set_visual_state(
                    self, enumerate_windows_and_processes=False, idle=False
                ):
                    if not self.pl.monitoring:
                        return
                    if debug > 1:
                        print(
                            "[DEBUG] set_visual_state(enumerate_windows_and_processes=%s, idle=%s)"
                            % (enumerate_windows_and_processes, idle)
                        )
                    self.SetIcon(
                        self.get_icon(enumerate_windows_and_processes, idle),
                        self.pl.get_title(),
                    )
                    if debug > 1:
                        print("[DEBUG] /set_visual_state")

                def show_notification(
                    self,
                    text=None,
                    sticky=False,
                    show_notification=True,
                    flags=wx.ICON_INFORMATION,
                    toggle=False,
                ):
                    if wx.VERSION < (3,) or not self.pl._check_keep_running():
                        wx.Bell()
                        return
                    if debug > 1:
                        print(
                            "[DEBUG] show_notification(text=%r, sticky=%s, show_notification=%s, flags=%r, toggle=%s)"
                            % (text, sticky, show_notification, flags, toggle)
                        )
                    if (sticky or text) and show_notification:
                        # Do not show notification unless enabled
                        show_notification = getcfg("profile_loader.show_notifications")
                    if sticky:
                        self.balloon_text = text
                        self.flags = flags
                    elif text:
                        self.balloon_text = None
                        self.flags = 0
                    else:
                        text = self.balloon_text
                        flags = self.flags or flags
                    if not text:
                        if (
                            "--force" not in sys.argv[1:]
                            and calibration_management_isenabled()
                        ):
                            text = lang.getstr("calibration.load.handled_by_os") + "\n"
                        else:
                            text = ""
                        if self.pl._component_name:
                            text += (
                                lang.getstr("app.detected", self.pl._component_name)
                                + "\n"
                            )
                        text += lang.getstr("profile_loader.info", self.pl.reload_count)
                        for i, (display, edid, moninfo, device) in enumerate(
                            self.pl.monitors
                        ):
                            if device:
                                devicekey = device.DeviceKey
                            else:
                                devicekey = None
                            key = devicekey or str(i)
                            (
                                profile_key,
                                mtime,
                                desc,
                            ) = self.pl.profile_associations.get(key, (False, 0, ""))
                            if profile_key is False:
                                desc = lang.getstr("unknown")
                            elif not profile_key:
                                desc = lang.getstr("unassigned").lower()
                            if (
                                self.pl.setgammaramp_success.get(i)
                                and self.pl._reset_gamma_ramps
                            ):
                                desc = (
                                    lang.getstr("linear").capitalize() + " / %s" % desc
                                )
                            elif (
                                not self.pl.setgammaramp_success.get(i)
                                or not profile_key
                            ):
                                desc = lang.getstr("unknown") + " / %s" % desc
                            display = display.replace(
                                "[PRIMARY]", lang.getstr("display.primary")
                            )
                            text += "\n%s: %s" % (display, desc)
                    if not show_notification:
                        if debug > 1:
                            print("[DEBUG] /show_notification")
                        return
                    if getattr(self, "_notification", None):
                        self._notification.fade("out")
                        if toggle:
                            if debug > 1:
                                print("[DEBUG] /show_notification")
                            return
                    bitmap = wx.BitmapFromIcon(self.get_icon())
                    self._notification = TaskBarNotification(
                        bitmap, self.pl.get_title(), text
                    )
                    if debug > 1:
                        print("[DEBUG] /show_notification")

            self.taskbar_icon = TaskBarIcon(self)

            try:
                self.gdi32 = ctypes.windll.gdi32
                self.gdi32.GetDeviceGammaRamp.restype = ctypes.c_bool
                self.gdi32.SetDeviceGammaRamp.restype = ctypes.c_bool
            except Exception as exception:
                self.gdi32 = None
                print(exception)
                self.taskbar_icon.show_notification(str(exception))

            if self.use_madhcnet:
                try:
                    self.madvr = madvr.MadTPG()
                except Exception as exception:
                    print(exception)
                    if str(exception) != lang.getstr("madvr.not_found"):
                        self.taskbar_icon.show_notification(str(exception))
                else:
                    self.madvr.add_connection_callback(
                        self._madvr_connection_callback, None, "madVR"
                    )
                    self.madvr.add_connection_callback(
                        self._madvr_connection_callback, None, "madTPG"
                    )
                    self.madvr.listen()
                    self.madvr.announce()

            self.frame = PLFrame(self)
            self.frame.listen()

            self._check_keep_running()

            self._check_display_conf_thread = threading.Thread(
                target=self._check_display_conf_wrapper,
                name="DisplayConfigurationMonitoring",
            )
            self._check_display_conf_thread.start()

            if app:
                app.TopWindow = self.frame
                app.MainLoop()

    def apply_profiles(self, event=None, index=None):
        from DisplayCAL.util_os import dlopen, which
        from DisplayCAL.worker import Worker, get_argyll_util

        if sys.platform == "win32":
            self.lock.acquire()

        worker = Worker()

        errors = []

        if sys.platform == "win32":
            separator = "-"
        else:
            separator = "="
        print(separator * 80)
        print(lang.getstr("calibration.loading_from_display_profile"))

        # dispwin sets the _ICC_PROFILE(_n) root window atom, per-output xrandr
        # _ICC_PROFILE property (if xrandr is working) and loads the vcgt for the
        # requested screen (ucmm backend using color.jcnf), and has to be called
        # multiple times to setup multiple screens.
        #
        # If there is no profile configured in ucmm for the requested screen (or
        # ucmm support has been removed, like in the Argyll CMS versions shipped by
        # recent Fedora releases), it falls back to a possibly existing per-output
        # xrandr _ICC_PROFILE property (if xrandr is working) or _ICC_PROFILE(_n)
        # root window atom.
        dispwin = get_argyll_util("dispwin")
        if index is None:
            if dispwin:
                worker.enumerate_displays_and_ports(
                    silent=True,
                    check_lut_access=False,
                    enumerate_ports=False,
                    include_network_devices=False,
                )
                self.monitors = []
                if sys.platform == "win32" and worker.displays:
                    self._enumerate_monitors()
            else:
                errors.append(lang.getstr("argyll.util.not_found", "dispwin"))

        if sys.platform != "win32":
            # gcm-apply sets the _ICC_PROFILE root window atom for the first screen,
            # per-output xrandr _ICC_PROFILE properties (if xrandr is working) and
            # loads the vcgt for all configured screens (device-profiles.conf)
            # NOTE: gcm-apply is no longer part of GNOME Color Manager since the
            # introduction of colord as it's no longer needed
            gcm_apply = which("gcm-apply")
            if gcm_apply:
                worker.exec_cmd(
                    gcm_apply, capture_output=True, skip_scripts=True, silent=False
                )

            # oyranos-monitor sets _ICC_PROFILE(_n) root window atoms (oyranos
            # db backend) and loads the vcgt for all configured screens when
            # xcalib is installed
            oyranos_monitor = which("oyranos-monitor")
            xcalib = which("xcalib")

        argyll_use_colord = os.getenv("ARGYLL_USE_COLORD") and dlopen(
            "libcolordcompat.so"
        )

        results = []
        for i, display in enumerate(
            [
                display.replace("[PRIMARY]", lang.getstr("display.primary"))
                for display in worker.displays
            ]
        ):
            if config.is_virtual_display(i) or (index is not None and i != index):
                continue
            # Load profile and set vcgt
            if sys.platform != "win32" and oyranos_monitor:
                display_conf_oy_compat = worker.check_display_conf_oy_compat(i + 1)
                if display_conf_oy_compat:
                    worker.exec_cmd(
                        oyranos_monitor,
                        [
                            "-x",
                            str(worker.display_rects[i][0]),
                            "-y",
                            str(worker.display_rects[i][1]),
                        ],
                        capture_output=True,
                        skip_scripts=True,
                        silent=False,
                    )
            if dispwin:
                if not argyll_use_colord:
                    # Deal with colord ourself
                    profile_arg = worker.get_dispwin_display_profile_argument(i)
                else:
                    # Argyll deals with colord directly
                    profile_arg = "-L"
                if (
                    sys.platform == "win32"
                    or not oyranos_monitor
                    or not display_conf_oy_compat
                    or not xcalib
                    or profile_arg == "-L"
                ):
                    # Only need to run dispwin if under Windows, or if nothing else
                    # has already taken care of display profile and vcgt loading
                    # (e.g. oyranos-monitor with xcalib, or colord)
                    if worker.exec_cmd(
                        dispwin,
                        ["-v", "-d%i" % (i + 1), profile_arg],
                        capture_output=True,
                        skip_scripts=True,
                        silent=False,
                    ):
                        errortxt = ""
                    else:
                        errortxt = "\n".join(worker.errors).strip()
                    if errortxt and (
                        (
                            "using linear" not in errortxt
                            and "assuming linear" not in errortxt
                        )
                        or len(errortxt.split("\n")) > 1
                    ):
                        if "Failed to get the displays current ICC profile" in errortxt:
                            # Maybe just not configured
                            continue
                        elif (
                            sys.platform == "win32"
                            or "Failed to set VideoLUT" in errortxt
                            or "We don't have access to the VideoLUT" in errortxt
                        ):
                            errstr = lang.getstr("calibration.load_error")
                        else:
                            errstr = lang.getstr("profile.load_error")
                        errors.append(": ".join([display, errstr]))
                        continue
                    else:
                        results.append(display)
                if (
                    config.getcfg("profile_loader.verify_calibration")
                    or "--verify" in sys.argv[1:]
                ):
                    # Verify the calibration was actually loaded
                    worker.exec_cmd(
                        dispwin,
                        ["-v", "-d%i" % (i + 1), "-V", profile_arg],
                        capture_output=True,
                        skip_scripts=True,
                        silent=False,
                    )
                    # The 'NOT loaded' message goes to stdout!
                    # Other errors go to stderr
                    errortxt = "\n".join(worker.errors + worker.output).strip()
                    if (
                        "NOT loaded" in errortxt
                        or "We don't have access to the VideoLUT" in errortxt
                    ):
                        errors.append(
                            ": ".join([display, lang.getstr("calibration.load_error")])
                        )

        if sys.platform == "win32":
            self.lock.release()
            if event:
                self.notify(results, errors)

        return errors

    def notify(self, results, errors, sticky=False, show_notification=False):
        wx.CallAfter(
            lambda: self and self._notify(results, errors, sticky, show_notification)
        )

    def _notify(self, results, errors, sticky=False, show_notification=False):
        if debug > 1:
            print(
                "[DEBUG] notify(results=%r, errors=%r, sticky=%s, show_notification=%s)"
                % (results, errors, sticky, show_notification)
            )
        self.taskbar_icon.set_visual_state()
        results.extend(errors)
        if errors:
            flags = wx.ICON_ERROR
        else:
            flags = wx.ICON_INFORMATION
        self.taskbar_icon.show_notification(
            "\n".join(results), sticky, show_notification, flags
        )
        if debug > 1:
            print("[DEBUG] /notify")

    def apply_profiles_and_warn_on_error(self, event=None, index=None):
        # wx.App must already be initialized at this point!
        errors = self.apply_profiles(event, index)
        if (
            errors
            and (
                config.getcfg("profile_loader.error.show_msg")
                or "--error-dialog" in sys.argv[1:]
            )
            and "--silent" not in sys.argv[1:]
        ):
            from DisplayCAL.wxwindows import InfoDialog, wx

            dlg = InfoDialog(
                None,
                msg="\n".join(errors),
                title=self.get_title(),
                ok=lang.getstr("ok"),
                bitmap=config.geticon(32, "dialog-error"),
                show=False,
            )
            dlg.SetIcons(
                config.get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )
            dlg.do_not_show_again_cb = wx.CheckBox(
                dlg, -1, lang.getstr("dialog.do_not_show_again")
            )
            dlg.do_not_show_again_cb.SetValue(
                not bool(config.getcfg("profile_loader.error.show_msg"))
            )

            def do_not_show_again_handler(event=None):
                config.setcfg(
                    "profile_loader.error.show_msg",
                    int(not dlg.do_not_show_again_cb.GetValue()),
                )
                config.writecfg(
                    module="apply-profiles",
                    options=("argyll.dir", "profile.load_on_login", "profile_loader"),
                )

            dlg.do_not_show_again_cb.Bind(wx.EVT_CHECKBOX, do_not_show_again_handler)
            dlg.sizer3.Add(dlg.do_not_show_again_cb, flag=wx.TOP, border=12)
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            dlg.Center(wx.BOTH)
            dlg.ok.SetDefault()
            dlg.ShowModalThenDestroy()

    def elevate(self):
        if sys.getwindowsversion() >= (6,):
            from win32com.shell import shell as win32com_shell
            from win32con import SW_SHOW

            loader_args = []
            if os.path.basename(exe).lower() in ("python.exe", "pythonw.exe"):
                # cmd = os.path.join(exedir, "pythonw.exe")
                cmd = exe
                pyw = os.path.normpath(
                    os.path.join(pydir, "..", appname + "-apply-profiles.pyw")
                )
                if os.path.exists(pyw):
                    # Running from source or 0install
                    # Check if this is a 0install implementation, in which
                    # case we want to call 0launch with the appropriate
                    # command
                    if re.match(
                        r"sha\d+(?:new)?", os.path.basename(os.path.dirname(pydir))
                    ):
                        cmd = which("0install-win.exe") or "0install-win.exe"
                        loader_args.extend(
                            [
                                "run",
                                "--batch",
                                "--no-wait",
                                "--offline",
                                "--command=run-apply-profiles",
                                f"http://{DOMAIN}/0install/{appname}.xml",
                            ]
                        )
                    else:
                        # Running from source
                        loader_args.append(pyw)
                else:
                    # Regular install
                    loader_args.append(
                        get_data_path(
                            "/".join(["scripts", appname + "-apply-profiles"])
                        )
                    )
            else:
                cmd = os.path.join(pydir, appname + "-apply-profiles.exe")
            loader_args.append("--profile-associations")
            try:
                run_as_admin(cmd, loader_args)
            except pywintypes.error as exception:
                if exception.args[0] != winerror.ERROR_CANCELLED:
                    show_result_dialog(exception)
            else:
                self.shutdown()
                wx.CallLater(50, self.exit)
                return True

    def exit(self, event=None):
        print("Executing ProfileLoader.exit(%s)" % event)
        dlg = None
        for dlg in get_dialogs():
            if not isinstance(dlg, ProfileLoaderExceptionsDialog) or (
                event and hasattr(event, "CanVeto") and not event.CanVeto()
            ):
                try:
                    dlg.EndModal(wx.ID_CANCEL)
                except Exception:
                    pass
                else:
                    dlg = None
            if dlg and event and hasattr(event, "CanVeto") and event.CanVeto():
                # Need to request user attention for all open
                # dialogs because calling it only on the topmost
                # one does not guarantee taskbar flash
                dlg.RequestUserAttention()
        else:
            if dlg and event and hasattr(event, "CanVeto") and event.CanVeto():
                event.Veto()
                print("Vetoed", event)
                return
        if (
            event
            and self.frame
            and event.GetEventType() == wx.EVT_MENU.typeId
            and (
                not calibration_management_isenabled()
                or config.getcfg("profile_loader.fix_profile_associations")
            )
        ):
            dlg = ConfirmDialog(
                None,
                msg=lang.getstr("profile_loader.exit_warning"),
                title=self.get_title(),
                ok=lang.getstr("menuitem.quit"),
                bitmap=config.geticon(32, "dialog-warning"),
            )
            dlg.SetIcons(
                config.get_icon_bundle([256, 48, 32, 16], appname + "-apply-profiles")
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_OK:
                print("Cancelled ProfileLoader.exit(%s)" % event)
                return
        if isinstance(event, wx.CloseEvent):
            # Other event source
            event.Skip()
        else:
            # Called from menu
            wx.GetApp().ExitMainLoop()

    def get_title(self):
        title = "%s %s %s" % (
            appname,
            lang.getstr("profile_loader").title(),
            version_short,
        )
        if VERSION > VERSION_BASE:
            title += " Beta"
        if "--force" in sys.argv[1:]:
            title += " (%s)" % lang.getstr("forced")
        return title

    def _can_fix_profile_associations(self):
        """Check whether we can 'fix' profile associations or not.

        'Fixing' means we assign the profile of the actual active child device
        to the 1st child device so that applications using GetICMProfile get
        the correct profile (GetICMProfile always returns the profile of the
        1st child device irrespective if this device is active or not. This is
        a Windows bug).

        This only works if a child device is not attached to several adapters
        (which is something that can happen due to the inexplicable mess that
        is the Windows display enumeration API).

        """
        if not self.child_devices_count:
            for i, (display, edid, moninfo, device) in enumerate(self.monitors):
                child_devices = get_display_devices(moninfo["Device"])
                for child_device in child_devices:
                    if child_device.DeviceKey not in self.child_devices_count:
                        self.child_devices_count[child_device.DeviceKey] = 0
                    self.child_devices_count[child_device.DeviceKey] += 1
        return (
            bool(self.child_devices_count)
            and max(self.child_devices_count.values()) == 1
        )

    def _check_keep_running(self):
        windows = []
        # print '-' * 79
        try:
            win32gui.EnumThreadWindows(
                self._tid, self._enumerate_own_windows_callback, windows
            )
        except pywintypes.error as exception:
            pass
        windows.extend(
            [
                window
                for window in wx.GetTopLevelWindows()
                if not isinstance(window, wx.Dialog)
                and window.Name != "TaskBarNotification"
                and window.Name != "DisplayIdentification"
                and window.Name != "profile_info"
            ]
        )
        numwindows = len(windows)
        if numwindows < self.numwindows:
            # One of our windows has been closed by an external event
            # (i.e. WM_CLOSE). This is a hint that something external is trying
            # to get us to exit. Comply by closing our main top-level window to
            # initiate clean shutdown.
            print("Window count", self.numwindows, "->", numwindows)
            return False
        self.numwindows = numwindows
        return True

    def _enumerate_own_windows_callback(self, hwnd, windowlist):
        cls = win32gui.GetClassName(hwnd)
        # print cls
        if cls in (
            "madHcNetQueueWindow",
            "wxTLWHiddenParent",
            "wxTimerHiddenWindow",
            "wxDisplayHiddenWindow",
            "SysTrayIcon",
        ) or cls.startswith("madToolsMsgHandlerWindow"):
            windowlist.append(cls)

    def _display_changed(self, event):
        print(event)

        threading.Thread(
            target=self._process_display_changed, name="ProcessDisplayChangedEvent"
        ).start()

    def _process_display_changed(self):
        if self.lock.locked():
            print("ProcessDisplayChangedEvent: Waiting to acquire lock...")
        with self.lock:
            print("ProcessDisplayChangedEvent: Acquired lock")
            self._display_changed_event = True
            self._next = True
            if getattr(self, "profile_associations_dlg", None):
                wx.CallAfter(
                    wx.CallLater,
                    1000,
                    lambda: self.profile_associations_dlg
                    and self.profile_associations_dlg.update(True),
                )
            if getattr(self, "fix_profile_associations_dlg", None):
                wx.CallAfter(
                    wx.CallLater,
                    1000,
                    lambda: self.fix_profile_associations_dlg
                    and self.fix_profile_associations_dlg.update(True),
                )
            print("ProcessDisplayChangedEvent: Releasing lock")

    def _check_display_changed(self, first_run=False, dry_run=False):
        # Check registry if display configuration changed (e.g. if a display
        # was added/removed, and not just the resolution changed)
        if not (first_run or self._display_changed_event):
            # Not first run and no prior display changed event
            return False
        has_display_changed = False
        ts = time.time()
        key_name = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Configuration"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name)
            numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)
        except WindowsError as exception:
            # Windows XP or Win10 >= 1903 if not running elevated
            if exception.args[0] != errno.ENOENT or sys.getwindowsversion() >= (6,):
                warnings.warn(
                    r"Registry access failed: %s: HKLM\%s" % (str(exception), key_name),
                    Warning,
                )
            key = None
            numsubkeys = 0
            # get_active_display_devices takes around 3-10ms in contrast to
            # querying registry which takes 1-3ms
            if (
                not self._active_displays
                or self._active_displays != get_active_display_devices("DeviceKey")
            ):
                has_display_changed = True
        for i in range(numsubkeys):
            try:
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)
            except WindowsError as exception:
                warnings.warn(
                    r"Registry access failed: %s: HKLM\%s\%s"
                    % (str(exception), key_name, subkey_name),
                    Warning,
                )
                continue
            value_name = "SetId"
            try:
                display = winreg.QueryValueEx(subkey, "SetId")[0]
                value_name = "Timestamp"
                timestamp = struct.unpack(
                    "<Q", winreg.QueryValueEx(subkey, "Timestamp")[0].rjust(8, "0")
                )
            except WindowsError as exception:
                warnings.warn(
                    r"Registry access failed: %s: %s (HKLM\%s\%s)"
                    % (str(exception), value_name, key_name, subkey_name),
                    Warning,
                )
                continue
            if timestamp > self._current_timestamp:
                if display != self._current_display:
                    has_display_changed = True
                if not dry_run:
                    self._current_display = display
                    self._current_timestamp = timestamp
            winreg.CloseKey(subkey)
        if key:
            winreg.CloseKey(key)
        print(
            "Display configuration change detection took %.6f ms"
            % ((time.time() - ts) * 1000.0)
        )
        if not dry_run:
            # Display conf or resolution change
            self._enumerate_monitors()
        if has_display_changed:
            # First run or display conf change, not just resolution
            if not (first_run or dry_run):
                print(lang.getstr("display_detected"))
            if not dry_run:
                if getcfg("profile_loader.fix_profile_associations"):
                    # Work-around long-standing bug in applications
                    # querying the monitor profile not making sure
                    # to use the active display (this affects Windows
                    # itself as well) when only one display is
                    # active in a multi-monitor setup.
                    if not first_run:
                        self._reset_display_profile_associations()
                    self._set_display_profiles()
            if not (first_run or dry_run) and self._is_displaycal_running():
                # Normally calibration loading is disabled while
                # DisplayCAL is running. Override this when the
                # display has changed
                self._manual_restore = getcfg("profile.load_on_login") and 2
        if not dry_run:
            self._has_display_changed = has_display_changed
            self._display_changed_event = False
        return has_display_changed

    def _check_display_conf_wrapper(self):
        try:
            self._check_display_conf()
        except Exception as exception:
            if self.lock.locked():
                self.lock.release()
            wx.CallAfter(self._handle_fatal_error, traceback.format_exc())

    def _handle_fatal_error(self, exception):
        handle_error(exception)
        wx.CallAfter(self.exit)

    def _check_display_conf(self):
        display = None
        self._current_display = None
        self._current_timestamp = 0
        self._next = False
        first_run = True
        apply_profiles = self._should_apply_profiles()
        displaycal_running = False
        previous_hwnds_pids = self._hwnds_pids
        while self and self.monitoring:
            result = None
            results = []
            errors = []
            idle = True
            locked = self.lock.locked()
            if locked:
                print(
                    "DisplayConfigurationMonitoringThread: Waiting to acquire lock..."
                )
            self.lock.acquire()
            if locked:
                print("DisplayConfigurationMonitoringThread: Acquired lock")
            # Check if display configuration changed
            self._check_display_changed(first_run)
            # Check profile associations
            profile_associations_changed = 0
            for i, (display, edid, moninfo, device) in enumerate(self.monitors):
                display_desc = display.replace(
                    "[PRIMARY]", lang.getstr("display.primary")
                )
                if device:
                    devicekey = device.DeviceKey
                else:
                    devicekey = None
                key = devicekey or str(i)
                self._current_display_key = key
                exception = None
                profile_path = profile_name = None
                try:
                    profile_path = ICCP.get_display_profile(
                        i, path_only=True, devicekey=devicekey
                    )
                except IndexError:
                    if debug:
                        print("Display %s (%s) no longer present?" % (key, display))
                    self._next = False
                    break
                except Exception as exception:
                    if (
                        exception.args[0] != errno.ENOENT
                        and exception.args != self._last_exception_args
                    ) or debug:
                        self._last_exception_args = exception.args
                        print(
                            "Could not get display profile for display "
                            "%s (%s):" % (key, display),
                            exception,
                        )
                    if exception.args[0] == errno.ENOENT:
                        # Unassigned - don't show error icon
                        self.setgammaramp_success[i] = True
                        exception = None
                    else:
                        self.setgammaramp_success[i] = None
                else:
                    if profile_path:
                        profile_name = os.path.basename(profile_path)
                profile_key = str(profile_name or exception or "")
                association = self.profile_associations.get(key, (False, 0, ""))
                if (
                    getcfg("profile_loader.fix_profile_associations")
                    and not first_run
                    and not self._has_display_changed
                    and not self._next
                    and association[0] != profile_key
                ):
                    # At this point we do not yet know if only the profile
                    # association has changed or the display configuration.
                    # One second delay to allow display configuration
                    # to settle
                    if not self._check_display_changed(dry_run=True):
                        if debug:
                            print("Delay 1s")
                        timeout = 0
                        while (
                            self
                            and self.monitoring
                            and timeout < 1
                            and self._manual_restore != 2
                            and not self._next
                        ):
                            time.sleep(0.1)
                            timeout += 0.1
                        self._next = True
                    break
                if profile_path and os.path.isfile(profile_path):
                    mtime = os.stat(profile_path).st_mtime
                else:
                    mtime = 0
                profile_association_changed = False
                if association[:2] != (profile_key, mtime):
                    if profile_name is None:
                        desc = str(exception or "?")
                    else:
                        desc = get_profile_desc(profile_name)
                    if not first_run:
                        print("A profile change has been detected")
                        print(display, "->", desc)
                        device = get_active_display_device(moninfo["Device"])
                        if device:
                            display_edid = get_display_name_edid(device, moninfo, i)
                            if self.monitoring:
                                self.devices2profiles[device.DeviceKey] = (
                                    display_edid,
                                    profile_name,
                                    desc,
                                )
                        if (debug or verbose > 1) and device:
                            print(
                                "Monitor %s active display device name:"
                                % moninfo["Device"],
                                device.DeviceName,
                            )
                            print(
                                "Monitor %s active display device string:"
                                % moninfo["Device"],
                                device.DeviceString,
                            )
                            print(
                                "Monitor %s active display device state flags: 0x%x"
                                % (moninfo["Device"], device.StateFlags)
                            )
                            print(
                                "Monitor %s active display device ID:"
                                % moninfo["Device"],
                                device.DeviceID,
                            )
                            print(
                                "Monitor %s active display device key:"
                                % moninfo["Device"],
                                device.DeviceKey,
                            )
                        elif debug or verbose > 1:
                            print(
                                "WARNING: Monitor %s has no active display device"
                                % moninfo["Device"]
                            )
                    self.profile_associations[key] = (profile_key, mtime, desc)
                    self.profiles[key] = None
                    self.ramps[key] = (None, None, None)
                    profile_association_changed = True
                    profile_associations_changed += 1
                    if not first_run and self._is_displaycal_running():
                        # Normally calibration loading is disabled while
                        # DisplayCAL is running. Override this when the
                        # display has changed
                        self._manual_restore = getcfg("profile.load_on_login") and 2
                else:
                    desc = association[2]
                # Check video card gamma table and (re)load calibration if
                # necessary
                if not self.gdi32 or not (profile_name or self._reset_gamma_ramps):
                    continue
                apply_profiles = self._should_apply_profiles()
                recheck = False
                (vcgt_ramp, vcgt_ramp_hack, vcgt_values) = self.ramps.get(
                    self._reset_gamma_ramps or key, (None, None, None)
                )
                if not vcgt_ramp:
                    vcgt_values = ([], [], [])
                    if not self._reset_gamma_ramps:
                        # Get display profile
                        if not self.profiles.get(key):
                            try:
                                self.profiles[key] = ICCP.ICCProfile(profile_name)
                                if (
                                    isinstance(
                                        self.profiles[key].tags.get("MS00"),
                                        ICCP.WcsProfilesTagType,
                                    )
                                    and "vcgt" not in self.profiles[key].tags
                                ):
                                    self.profiles[key].tags["vcgt"] = (
                                        self.profiles[key].tags["MS00"].get_vcgt()
                                    )
                                self.profiles[key].tags.get("vcgt")
                            except Exception as exception:
                                print(exception)
                                self.profiles[key] = ICCP.ICCProfile()
                        profile = self.profiles[key]
                        if isinstance(
                            profile.tags.get("vcgt"), ICCP.VideoCardGammaType
                        ):
                            # Get display profile vcgt
                            vcgt_values = profile.tags.vcgt.get_values()[:3]
                            # Quantize to n bits
                            # 8 bits can be encoded accurately in a 256-entry
                            # 16 bit vcgt, but all other bitdepths need to be
                            # quantized in such a way that the encoded 16-bit
                            # values lie as close as possible to the ideal ones.
                            # We assume the graphics subsystem quantizes using
                            # integer truncating from the 16 bit encoded value
                            if self._quantize < 65535.0:
                                smooth = str(
                                    getcfg("profile_loader.quantize_bits")
                                ) in getcfg("profile_loader.smooth_bits").split(";")
                                smooth_window = (0.5, 1, 1, 1, 0.5)
                                for points in vcgt_values:
                                    quantized = [
                                        round(point[1] / 65535.0 * self._quantize)
                                        for point in points
                                    ]
                                    if smooth:
                                        # Smooth and round to nearest again
                                        quantized = [
                                            round(v)
                                            for v in smooth_avg(
                                                quantized, 1, smooth_window
                                            )
                                        ]
                                    for k, point in enumerate(points):
                                        point[1] = int(
                                            math.ceil(
                                                quantized[k] / self._quantize * 65535
                                            )
                                        )
                    if len(vcgt_values[0]) != 256:
                        # Hmm. Do we need to deal with this?
                        # I've never seen table-based vcgt with != 256 entries
                        if (
                            not self._reset_gamma_ramps
                            and (self._manual_restore or profile_association_changed)
                            and profile.tags.get("vcgt")
                        ):
                            print(
                                lang.getstr("calibration.loading_from_display_profile")
                            )
                            print(display_desc)
                            print(
                                lang.getstr(
                                    "vcgt.unknown_format",
                                    os.path.basename(profile.fileName),
                                )
                            )
                            print(lang.getstr("failure"))
                            results.append(display_desc)
                            errors.append(
                                lang.getstr(
                                    "vcgt.unknown_format",
                                    os.path.basename(profile.fileName),
                                )
                            )
                        # Fall back to linear calibration
                        tagData = "vcgt"
                        tagData += "\0" * 4  # Reserved
                        tagData += "\0\0\0\x01"  # Formula type
                        for channel in range(3):
                            tagData += "\0\x01\0\0"  # Gamma 1.0
                            tagData += "\0" * 4  # Min 0.0
                            tagData += "\0\x01\0\0"  # Max 1.0
                        vcgt = ICCP.VideoCardGammaFormulaType(tagData, "vcgt")
                        vcgt_values = vcgt.get_values()[:3]
                        if self._reset_gamma_ramps:
                            print("Caching linear gamma ramps")
                        else:
                            print(
                                "Caching implicit linear gamma ramps for profile", desc
                            )
                    else:
                        print("Caching gamma ramps for profile", desc)
                    # Convert vcgt to ushort_Array_256_Array_3
                    vcgt_ramp = ((ctypes.c_ushort * 256) * 3)()
                    vcgt_ramp_hack = ((ctypes.c_ushort * 256) * 3)()
                    for j in range(len(vcgt_values[0])):
                        for k in range(3):
                            vcgt_value = vcgt_values[k][j][1]
                            vcgt_ramp[k][j] = vcgt_value
                            # Some video drivers won't reload gamma ramps if
                            # the previously loaded calibration was the same.
                            # Work-around by first loading a slightly changed
                            # gamma ramp.
                            if j == 0:
                                vcgt_value += 1
                            vcgt_ramp_hack[k][j] = vcgt_value
                    self.ramps[self._reset_gamma_ramps or key] = (
                        vcgt_ramp,
                        vcgt_ramp_hack,
                        vcgt_values,
                    )
                    recheck = True
                if self._skip:
                    self.setgammaramp_success[i] = True
                if (
                    not apply_profiles
                    and self.__other_component[1] != "madHcNetQueueWindow"
                ):
                    # Important: Do not break here because we still want to
                    # detect changed profile associations
                    continue
                if getcfg("profile_loader.track_other_processes"):
                    hwnds_pids_changed = self._hwnds_pids != previous_hwnds_pids
                    if (
                        (debug or verbose > 1)
                        and hwnds_pids_changed
                        and previous_hwnds_pids
                    ):
                        print("List of running processes changed")
                        hwnds_pids_diff = previous_hwnds_pids.difference(
                            self._hwnds_pids
                        )
                        if hwnds_pids_diff:
                            print("Gone processes:")
                            for hwnd_pid in hwnds_pids_diff:
                                print(*hwnd_pid)
                        hwnds_pids_diff = self._hwnds_pids.difference(
                            previous_hwnds_pids
                        )
                        if hwnds_pids_diff:
                            print("New processes:")
                            for hwnd_pid in hwnds_pids_diff:
                                print(*hwnd_pid)
                else:
                    hwnds_pids_changed = getcfg(
                        "profile_loader.ignore_unchanged_gamma_ramps"
                    )
                if idle:
                    idle = (
                        not hwnds_pids_changed
                        and not self._manual_restore
                        and not profile_association_changed
                    )
                if (
                    not self._manual_restore
                    and not profile_association_changed
                    and (idle or self.__other_component[1] == "madHcNetQueueWindow")
                    and getcfg("profile_loader.check_gamma_ramps")
                ):
                    # Get video card gamma ramp
                    try:
                        hdc = win32gui.CreateDC(moninfo["Device"], None, None)
                    except Exception as exception:
                        if exception.args != self._last_exception_args or debug:
                            self._last_exception_args = exception.args
                            print(
                                "Couldn't create DC for",
                                moninfo["Device"],
                                "(%s)" % display,
                            )
                        continue
                    ramp = ((ctypes.c_ushort * 256) * 3)()
                    try:
                        result = self.gdi32.GetDeviceGammaRamp(hdc, ramp)
                    except Exception:
                        continue
                    finally:
                        win32gui.DeleteDC(hdc)
                    if not result:
                        continue
                    # Get ramp values
                    values = ([], [], [])
                    for j, channel in enumerate(ramp):
                        for k, v in enumerate(channel):
                            values[j].append([float(k), v])
                    if self.__other_component[1] == "madHcNetQueueWindow":
                        madvr_reset_cal = self._madvr_reset_cal.get(key, True)
                        if not madvr_reset_cal and values == self.linear_vcgt_values:
                            # madVR has reset vcgt
                            self._madvr_reset_cal[key] = True
                            print(
                                "madVR did reset gamma ramps for %s, "
                                "do not preserve calibration state" % display
                            )
                        elif (
                            madvr_reset_cal
                            and values == vcgt_values
                            and values != self.linear_vcgt_values
                        ):
                            # madVR did not reset vcgt
                            self._madvr_reset_cal[key] = False
                            print(
                                "madVR did not reset gamma ramps for %s, "
                                "preserve calibration state" % display
                            )
                            self.setgammaramp_success[i] = True
                        if self._madvr_reset_cal.get(key, True) != madvr_reset_cal:
                            if self._madvr_reset_cal.get(key, True):
                                msg = lang.getstr(
                                    "app.detected.calibration_loading_disabled",
                                    self._component_name,
                                )
                                self.notify([msg], [], True, False)
                                continue
                            else:
                                self.notify([], [], True, False)
                    # Check if video card matches profile vcgt
                    if (
                        not hwnds_pids_changed
                        and values == vcgt_values
                        and i in self.setgammaramp_success
                    ):
                        idle = True
                        continue
                    idle = False
                    if apply_profiles and not hwnds_pids_changed:
                        print(lang.getstr("vcgt.mismatch", display_desc))
                is_buggy_video_driver = self._is_buggy_video_driver(moninfo)
                if recheck:
                    # Try and prevent race condition with madVR
                    # launching and resetting video card gamma table
                    apply_profiles = self._should_apply_profiles()
                if not apply_profiles or idle:
                    # Important: Do not break here because we still want to
                    # detect changed profile associations
                    continue
                if debug or verbose > 1:
                    if self._manual_restore:
                        print("Manual restore flag:", self._manual_restore)
                    if profile_association_changed:
                        print(
                            "Number of profile associations changed:",
                            profile_associations_changed,
                        )
                    if apply_profiles:
                        print("Apply profiles:", apply_profiles)
                # Now actually reload or reset calibration
                if (
                    self._manual_restore
                    or profile_association_changed
                    or (
                        not hwnds_pids_changed
                        and getcfg("profile_loader.check_gamma_ramps")
                    )
                ):
                    if self._reset_gamma_ramps:
                        print(lang.getstr("calibration.resetting"))
                        print(display_desc)
                    else:
                        print(lang.getstr("calibration.loading_from_display_profile"))
                        print("%s:" % display_desc, desc)
                elif verbose > 1 and getcfg("profile_loader.track_other_processes"):
                    print("Preserving calibration state for display", display)
                try:
                    hdc = win32gui.CreateDC(moninfo["Device"], None, None)
                except Exception as exception:
                    if exception.args != self._last_exception_args or debug:
                        self._last_exception_args = exception.args
                        print(
                            "Couldn't create DC for",
                            moninfo["Device"],
                            "(%s)" % display,
                        )
                    continue
                try:
                    if is_buggy_video_driver:
                        result = self.gdi32.SetDeviceGammaRamp(hdc, vcgt_ramp_hack)
                    result = self.gdi32.SetDeviceGammaRamp(hdc, vcgt_ramp)
                except Exception as exception:
                    result = exception
                finally:
                    win32gui.DeleteDC(hdc)
                self.setgammaramp_success[i] = (
                    result
                    and not isinstance(result, Exception)
                    and (self._reset_gamma_ramps or bool(self.profiles.get(key)))
                )
                if (
                    self._manual_restore
                    or profile_association_changed
                    or (
                        not hwnds_pids_changed
                        and getcfg("profile_loader.check_gamma_ramps")
                    )
                ):
                    if isinstance(result, Exception) or not result:
                        if result:
                            print(result)
                        print(lang.getstr("failure"))
                    else:
                        print(lang.getstr("success"))
                if self._manual_restore or (
                    profile_association_changed
                    and (isinstance(result, Exception) or not result)
                ):
                    if isinstance(result, Exception) or not result:
                        errstr = lang.getstr("calibration.load_error")
                        errors.append(": ".join([display_desc, errstr]))
                    else:
                        text = display_desc + ": "
                        if self._reset_gamma_ramps:
                            text += lang.getstr("linear").capitalize()
                        else:
                            text += desc
                        results.append(text)
            else:
                # We only arrive here if the loop was completed
                self._next = False
            if self._next:
                # We only arrive here if a change in profile associations was
                # detected and we exited the loop early
                if locked:
                    print("DisplayConfigurationMonitoringThread: Releasing lock")
                self.lock.release()
                if locked:
                    print("DisplayConfigurationMonitoringThread: Released lock")
                continue
            previous_hwnds_pids = self._hwnds_pids
            timestamp = time.time()
            localtime = list(time.localtime(self._timestamp))
            localtime[3:6] = 23, 59, 59
            midnight = time.mktime(localtime) + 1
            if timestamp >= midnight:
                self.reload_count = 0
                self._timestamp = timestamp
            if results or errors:
                if results:
                    self.reload_count += 1
                    if self._reset_gamma_ramps:
                        lstr = "calibration.reset_success"
                    else:
                        lstr = "calibration.load_success"
                    results.insert(0, lang.getstr(lstr))
                    if self._app_detection_msg:
                        results.insert(0, self._app_detection_msg)
                        self._app_detection_msg = None
                self.notify(
                    results,
                    errors,
                    show_notification=bool(not first_run or errors)
                    and self.__other_component[1] != "madHcNetQueueWindow",
                )
            else:
                # if (apply_profiles != self.__apply_profiles or
                # profile_associations_changed):
                if not idle:
                    if apply_profiles and (
                        not profile_associations_changed or not self._reset_gamma_ramps
                    ):
                        self.reload_count += 1
                if displaycal_running != self._is_displaycal_running():
                    if displaycal_running:
                        msg = lang.getstr(
                            "app.detection_lost.calibration_loading_enabled", appname
                        )
                    else:
                        msg = lang.getstr(
                            "app.detected.calibration_loading_disabled", appname
                        )
                    displaycal_running = self._is_displaycal_running()
                    print(msg)
                    self.notify([msg], [], displaycal_running, show_notification=False)
                elif (
                    apply_profiles != self.__apply_profiles
                    or profile_associations_changed
                ):
                    wx.CallAfter(lambda: self and self.taskbar_icon.set_visual_state())
            if apply_profiles and not idle:
                wx.CallAfter(lambda: self and self.taskbar_icon.animate())
            self.__apply_profiles = apply_profiles
            first_run = False
            if profile_associations_changed and not self._has_display_changed:
                if getattr(self, "profile_associations_dlg", None):
                    wx.CallAfter(
                        lambda: self.profile_associations_dlg
                        and self.profile_associations_dlg.update_profiles()
                    )
                if getattr(self, "fix_profile_associations_dlg", None):
                    wx.CallAfter(
                        lambda: self.fix_profile_associations_dlg
                        and self.fix_profile_associations_dlg.update()
                    )
            if result:
                self._has_display_changed = False
            self._manual_restore = False
            self._skip = False
            if locked:
                print("DisplayConfigurationMonitoringThread: Releasing lock")
            self.lock.release()
            if locked:
                print("DisplayConfigurationMonitoringThread: Released lock")
            if "--oneshot" in sys.argv[1:]:
                wx.CallAfter(self.exit)
                break
            elif "--profile-associations" in sys.argv[1:]:
                sys.argv.remove("--profile-associations")
                wx.CallAfter(self._set_profile_associations, None)
            # Wait three seconds
            timeout = 0
            while (
                self
                and self.monitoring
                and timeout < 3
                and not self._manual_restore
                and not self._next
            ):
                if round(timeout * 100) % 25 == 0 and not self._check_keep_running():
                    self.monitoring = False
                    wx.CallAfter(lambda: self.frame and self.frame.Close(force=True))
                    break
                time.sleep(0.1)
                timeout += 0.1
        print("Display configuration monitoring thread finished")
        self.shutdown()

    def shutdown(self):
        if self._shutdown:
            return
        self._shutdown = True
        print("Shutting down profile loader")
        if self.monitoring:
            print("Shutting down display configuration monitoring thread")
            self.monitoring = False
        if getcfg("profile_loader.fix_profile_associations"):
            self._reset_display_profile_associations()
        self.writecfg()
        if getattr(self, "taskbar_icon", None):
            if self.taskbar_icon.menu:
                self.taskbar_icon.menu.Destroy()
            self.taskbar_icon.RemoveIcon()
        if getattr(self, "frame", None):
            self.frame.listening = False

    def _enumerate_monitors(self):
        print("-" * 80)
        print("Enumerating display adapters and devices:")
        print("")
        self.adapters = dict(
            [(device.DeviceName, device) for device in get_display_devices(None)]
        )
        self.monitors = []
        self.display_devices = dict()
        self.child_devices_count = {}
        # Enumerate per-adapter devices
        for adapter in self.adapters:
            for i, device in enumerate(get_display_devices(adapter)):
                if not i:
                    device0 = device
                if device.DeviceKey in self.display_devices:
                    continue
                display, edid = get_display_name_edid(device)
                self.display_devices[device.DeviceKey] = [
                    display,
                    edid,
                    device,
                    device0,
                ]
        # Enumerate monitors
        try:
            monitors = get_real_display_devices_info()
        except Exception:
            import traceback

            print(traceback.format_exc())
            monitors = []
            self.setgammaramp_success[0] = False
        self._active_displays = []
        for i, moninfo in enumerate(monitors):
            if moninfo["Device"] == "WinDisc":
                # If e.g. we physically disconnect the display device, we will
                # get a 'WinDisc' temporary monitor we cannot do anything with
                # (MS, why is this not documented?)
                print("Skipping 'WinDisc' temporary monitor %i" % i)
                continue
            moninfo["_adapter"] = self.adapters.get(
                moninfo["Device"], ICCP.ADict({"DeviceString": moninfo["Device"][4:]})
            )
            if self._is_buggy_video_driver(moninfo):
                print(
                    "Buggy video driver detected: %s."
                    % moninfo["_adapter"].DeviceString,
                    "Gamma ramp hack activated.",
                )
            device = get_active_display_device(moninfo["Device"])
            if device:
                self._active_displays.append(device.DeviceKey)
            if debug or verbose > 1:
                print(
                    "Found monitor %i %s flags 0x%x"
                    % (i, moninfo["Device"], moninfo["Flags"])
                )
                if device:
                    print(
                        "Monitor %i active display device name:" % i, device.DeviceName
                    )
                    print(
                        "Monitor %i active display device string:" % i,
                        device.DeviceString,
                    )
                    print(
                        "Monitor %i active display device state flags: "
                        "0x%x" % (i, device.StateFlags)
                    )
                    print("Monitor %i active display device ID:" % i, device.DeviceID)
                    print("Monitor %i active display device key:" % i, device.DeviceKey)
                else:
                    print("WARNING: Monitor %i has no active display device" % i)
            # Get monitor descriptive string
            display, edid = get_display_name_edid(device, moninfo, i)
            if debug or verbose > 1:
                print("Monitor %i active display description:" % i, display)
                print(
                    "Enumerating 1st display device for monitor %i %s"
                    % (i, moninfo["Device"])
                )
            try:
                device0 = win32api.EnumDisplayDevices(moninfo["Device"], 0)
            except pywintypes.error as exception:
                print(
                    "EnumDisplayDevices(%r, 0) failed:" % moninfo["Device"], exception
                )
                device0 = None
            if (debug or verbose > 1) and device0:
                print("Monitor %i 1st display device name:" % i, device0.DeviceName)
                print("Monitor %i 1st display device string:" % i, device0.DeviceString)
                print(
                    "Monitor %i 1st display device state flags: 0x%x"
                    % (i, device0.StateFlags)
                )
                print("Monitor %i 1st display device ID:" % i, device0.DeviceID)
                print("Monitor %i 1st display device key:" % i, device0.DeviceKey)
            if device0:
                display0, edid0 = get_display_name_edid(device0)
                if debug or verbose > 1:
                    print("Monitor %i 1st display description:" % i, display0)
            if (
                device0
                and (not device or device0.DeviceKey != device.DeviceKey)
                and device0.DeviceKey not in self.display_devices
            ):
                # Key may not exist if device was added after enumerating
                # per-adapters devices
                self.display_devices[device0.DeviceKey] = [
                    display0,
                    edid0,
                    device0,
                    device0,
                ]
            if device:
                if device.DeviceKey in self.display_devices:
                    self.display_devices[device.DeviceKey][0] = display
                else:
                    # Key may not exist if device was added after enumerating
                    # per-adapters devices
                    self.display_devices[device.DeviceKey] = [
                        display,
                        edid,
                        device,
                        device0,
                    ]
            self.monitors.append((display, edid, moninfo, device))
        for display, edid, device, device0 in self.display_devices.values():
            if device.DeviceKey == device0.DeviceKey:
                device_name = "\\".join(device.DeviceName.split("\\")[:-1])
                print(
                    self.adapters.get(
                        device_name, ICCP.ADict({"DeviceString": device_name[4:]})
                    ).DeviceString
                )
            display_parts = display.split("@", 1)
            if len(display_parts) > 1:
                info = display_parts[1].split(" - ", 1)
                display_parts[1] = "@" + " ".join(info[:1])
            if not device.StateFlags & DISPLAY_DEVICE_ACTIVE:
                display_parts.append(" (%s)" % lang.getstr("deactivated"))
            print("  |-", "".join(display_parts))

    def _enumerate_windows_callback(self, hwnd, extra):
        cls = win32gui.GetClassName(hwnd)
        if cls == "madHcNetQueueWindow" or self._is_known_window_class(cls):
            try:
                thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
                filename = get_process_filename(pid)
            except pywintypes.error:
                return
            self._hwnds_pids.add((filename, pid, thread_id, hwnd))
            basename = os.path.basename(filename)
            if basename.lower() != "madhcctrl.exe" and pid != self._pid:
                self.__other_component = filename, cls, 0

    def _is_known_window_class(self, cls):
        for partial in self._known_window_classes:
            if partial in cls:
                return True

    def _is_buggy_video_driver(self, moninfo):
        # Intel video drivers won't reload gamma ramps if the
        # previously loaded calibration was the same.
        # Work-around by first loading a slightly changed
        # gamma ramp.
        adapter = moninfo["_adapter"].DeviceString.lower()
        for buggy_video_driver in self._buggy_video_drivers:
            if buggy_video_driver == "*" or buggy_video_driver in adapter:
                return True
        return False

    def _is_displaycal_running(self):
        displaycal_lockfile = os.path.join(confighome, appbasename + ".lock")
        return os.path.isfile(displaycal_lockfile)

    def _is_other_running(self, enumerate_windows_and_processes=True):
        """Determine if other software that may be using the videoLUT is in use
        (e.g. madVR video playback, madTPG, other calibration software)

        """
        if sys.platform != "win32":
            return
        self._is_other_running_lock.acquire()
        if enumerate_windows_and_processes:
            # At launch, we won't be able to determine if madVR is running via
            # the callback API, and we can only determine if another
            # calibration solution is running by enumerating windows and
            # processes anyway.
            other_component = self.__other_component
            self.__other_component = None, None, 0
            # Look for known window classes
            # Performance on C2D 3.16 GHz (Win7 x64, ~ 90 processes): ~ 1ms
            self._hwnds_pids = set()
            try:
                win32gui.EnumWindows(self._enumerate_windows_callback, None)
            except pywintypes.error as exception:
                print("Enumerating windows failed:", exception)
            if (
                not self.__other_component[1]
                or self.__other_component[1] == "madHcNetQueueWindow"
            ):
                # Look for known processes
                # Performance on C2D 3.16 GHz (Win7 x64, ~ 90 processes):
                # ~ 6-9ms (1ms to get PIDs)
                try:
                    processes = win32ts.WTSEnumerateProcesses()
                except pywintypes.error as exception:
                    print("Enumerating processes failed:", exception)
                else:
                    skip = False
                    for (session_id, pid, basename, user_security_id) in processes:
                        name_lower = basename.lower()
                        if name_lower != "madhcctrl.exe":
                            # Add all processes except madVR Home Cinema Control
                            self._hwnds_pids.add((basename, pid))
                        if skip or not user_security_id:
                            # Skip detection if other component already detected
                            # or no user security ID (if no user SID, it's a
                            # system process and we cannot get process filename
                            # due to access restrictions)
                            continue
                        known_app = name_lower in self._known_apps
                        has_exception = name_lower in self._exception_names
                        if not (known_app or has_exception):
                            continue
                        try:
                            filename = get_process_filename(pid)
                        except (WindowsError, pywintypes.error) as exception:
                            if exception.args[0] not in (
                                winerror.ERROR_ACCESS_DENIED,
                                winerror.ERROR_PARTIAL_COPY,
                                winerror.ERROR_INVALID_PARAMETER,
                                winerror.ERROR_GEN_FAILURE,
                            ):
                                print(
                                    "Couldn't get filename of " "process %s:" % pid,
                                    exception,
                                )
                            continue
                        enabled, reset, path = self._exceptions.get(
                            filename.lower(), (0, 0, "")
                        )
                        if known_app or enabled:
                            if known_app or not reset:
                                self.__other_component = filename, None, 0
                                skip = True
                            elif other_component != (filename, None, reset):
                                self._reset_gamma_ramps = True
                            self.__other_component = filename, None, reset
            if other_component != self.__other_component:
                if other_component[2] and not self.__other_component[2]:
                    self._reset_gamma_ramps = bool(
                        config.getcfg("profile_loader.reset_gamma_ramps")
                    )
                check = (not other_component[2] and not self.__other_component[2]) or (
                    other_component[2]
                    and self.__other_component[0:2] != (None, None)
                    and not self.__other_component[2]
                )
                if check:
                    if self.__other_component[0:2] == (None, None):
                        lstr = "app.detection_lost.calibration_loading_enabled"
                        component = other_component
                        sticky = False
                    else:
                        lstr = "app.detected.calibration_loading_disabled"
                        component = self.__other_component
                        sticky = True
                else:
                    if self.__other_component[0:2] != (None, None):
                        lstr = "app.detected"
                        component = self.__other_component
                    else:
                        lstr = "app.detection_lost"
                        component = other_component
                if component[1] == "madHcNetQueueWindow":
                    component_name = "madVR"
                    self._madvr_reset_cal = {}
                elif component[0]:
                    component_name = os.path.basename(component[0])
                    try:
                        info = list(
                            get_file_info(component[0])["StringFileInfo"].values()
                        )
                    except Exception:
                        info = None
                    if info:
                        # Use FileDescription over ProductName (the former may
                        # be more specific, e.g. Windows Display Color
                        # Calibration, the latter more generic, e.g. Microsoft
                        # Windows)
                        component_name = info[0].get(
                            "FileDescription",
                            info[0].get("ProductName", component_name),
                        )
                else:
                    component_name = lang.getstr("unknown")
                if self.__other_component[0:2] != (None, None):
                    self._component_name = component_name
                else:
                    self._component_name = None
                msg = lang.getstr(lstr, component_name)
                print(msg)
                if check:
                    self.notify(
                        [msg], [], sticky, show_notification=component_name != "madVR"
                    )
                else:
                    self._app_detection_msg = msg
                    self._manual_restore = getcfg("profile.load_on_login") and 2
        result = (
            self.__other_component[0:2] != (None, None)
            and not self.__other_component[2]
        )
        self._is_other_running_lock.release()
        if self.__other_component[1] == "madHcNetQueueWindow":
            if enumerate_windows_and_processes:
                # Check if gamma ramps were reset for current display
                return self._madvr_reset_cal.get(self._current_display_key, True)
            else:
                # Check if gamma ramps were reset for any display
                return len(self._madvr_reset_cal) < len(self.monitors) or True in list(
                    self._madvr_reset_cal.values()
                )
        return result

    def _madvr_connection_callback(
        self, param, connection, ip, pid, module, component, instance, is_new_instance
    ):
        if self.lock.locked():
            print("Waiting to acquire lock...")
        with self.lock:
            print("Acquired lock")
            if ip in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"):
                args = (param, connection, ip, pid, module, component, instance)
                try:
                    filename = get_process_filename(pid)
                except Exception:
                    filename = lang.getstr("unknown")
                if is_new_instance:
                    apply_profiles = self._should_apply_profiles(manual_override=None)
                    self._madvr_instances.append(args)
                    self.__other_component = filename, "madHcNetQueueWindow", 0
                    print("madVR instance connected:", "PID", pid, filename)
                    if apply_profiles:
                        msg = lang.getstr(
                            "app.detected.calibration_loading_disabled", component
                        )
                        print(msg)
                        self.notify([msg], [], True, show_notification=False)
                    wx.CallAfter(wx.CallLater, 1500, self._check_madvr_reset_cal, args)
                elif args in self._madvr_instances:
                    self._madvr_instances.remove(args)
                    print("madVR instance disconnected:", "PID", pid, filename)
                    if not self._madvr_instances and self._should_apply_profiles(
                        manual_override=None
                    ):
                        msg = lang.getstr(
                            "app.detection_lost.calibration_loading_enabled", component
                        )
                        print(msg)
                        self.notify([msg], [], show_notification=False)
            print("Releasing lock")

    def _check_madvr_reset_cal(self, madvr_instance):
        if madvr_instance not in self._madvr_instances:
            return
        # Check if madVR did reset the video card gamma tables.
        # If it didn't, assume we can keep preserving calibration state
        with self.lock:
            self._next = True

    def _reset_display_profile_associations(self):
        if not self._can_fix_profile_associations():
            return
        for devicekey in self.devices2profiles:
            display_edid, profile, desc = self.devices2profiles[devicekey]
            if devicekey in self._fixed_profile_associations and profile:
                try:
                    current_profile = ICCP.get_display_profile(
                        path_only=True, devicekey=devicekey
                    )
                except Exception as exception:
                    print(
                        "Could not get display profile for display "
                        "device %s (%s):" % (devicekey, display_edid[0]),
                        exception,
                    )
                    continue
                if not current_profile:
                    continue
                current_profile = os.path.basename(current_profile)
                if current_profile and current_profile != profile:
                    print(
                        "Resetting profile association for %s:" % display_edid[0],
                        current_profile,
                        "->",
                        profile,
                    )
                    try:
                        if not is_superuser() and not per_user_profiles_isenabled(
                            devicekey=devicekey
                        ):
                            # Can only associate profiles to the display if
                            # per-user-profiles are enabled or if running as admin
                            enable_per_user_profiles(devicekey=devicekey)
                        ICCP.set_display_profile(profile, devicekey=devicekey)
                        ICCP.unset_display_profile(current_profile, devicekey=devicekey)
                    except WindowsError as exception:
                        print(exception)

    def _set_display_profiles(self, dry_run=False):
        if not self._can_fix_profile_associations():
            return
        if debug or verbose > 1:
            print("-" * 80)
            print("Checking profile associations")
            print("")
        self.devices2profiles = {}
        for i, (display, _edid, moninfo, device) in enumerate(self.monitors):
            if debug or verbose > 1:
                print(
                    "Enumerating display devices for monitor %i %s"
                    % (i, moninfo["Device"])
                )
            devices = get_display_devices(moninfo["Device"])
            if not devices:
                if debug or verbose > 1:
                    print("WARNING: Monitor %i has no display devices" % i)
                continue
            active_device = get_active_display_device(None, devices=devices)
            if debug or verbose > 1:
                if active_device:
                    print(
                        "Monitor %i active display device name:" % i,
                        active_device.DeviceName,
                    )
                    print(
                        "Monitor %i active display device string:" % i,
                        active_device.DeviceString,
                    )
                    print(
                        "Monitor %i active display device state flags: "
                        "0x%x" % (i, active_device.StateFlags)
                    )
                    print(
                        "Monitor %i active display device ID:" % i,
                        active_device.DeviceID,
                    )
                    print(
                        "Monitor %i active display device key:" % i,
                        active_device.DeviceKey,
                    )
                else:
                    print("WARNING: Monitor %i has no active display device" % i)
            for device in devices:
                if active_device and device.DeviceID == active_device.DeviceID:
                    active_moninfo = moninfo
                else:
                    active_moninfo = None
                display_edid = get_display_name_edid(device, active_moninfo)
                try:
                    profile = ICCP.get_display_profile(
                        path_only=True, devicekey=device.DeviceKey
                    )
                except Exception as exception:
                    print(
                        "Could not get display profile for display "
                        "device %s (%s):" % (device.DeviceKey, display_edid[0]),
                        exception,
                    )
                    profile = None
                if profile:
                    profile = os.path.basename(profile)
                self.devices2profiles[device.DeviceKey] = (
                    display_edid,
                    profile,
                    get_profile_desc(profile),
                )
                if debug or verbose > 1:
                    print("%s (%s): %s" % (display_edid[0], device.DeviceKey, profile))
            # Set the active profile
            device = active_device
            if not device:
                continue
            try:
                correct_profile = ICCP.get_display_profile(
                    path_only=True, devicekey=device.DeviceKey
                )
            except Exception as exception:
                print(
                    "Could not get display profile for active display "
                    "device %s (%s):" % (device.DeviceKey, display),
                    exception,
                )
                continue
            if correct_profile:
                correct_profile = os.path.basename(correct_profile)
            device = devices[0]
            current_profile = self.devices2profiles[device.DeviceKey][1]
            if correct_profile and current_profile != correct_profile and not dry_run:
                print(
                    "Fixing profile association for %s:" % display,
                    current_profile,
                    "->",
                    correct_profile,
                )
                try:
                    if not is_superuser() and not per_user_profiles_isenabled(
                        devicekey=device.DeviceKey
                    ):
                        # Can only associate profiles to the display if
                        # per-user-profiles are enabled or if running as admin
                        enable_per_user_profiles(devicekey=device.DeviceKey)
                    ICCP.set_display_profile(
                        os.path.basename(correct_profile), devicekey=device.DeviceKey
                    )
                except WindowsError as exception:
                    print(exception)
                else:
                    self._fixed_profile_associations.add(device.DeviceKey)

    def _set_manual_restore(self, event, manual_restore=True):
        if event:
            print("Menu command:", end=" ")
        print("Set calibration state to load profile vcgt")
        if self.lock.locked():
            print("Waiting to acquire lock...")
        with self.lock:
            print("Acquired lock")
            setcfg("profile_loader.reset_gamma_ramps", 0)
            self._manual_restore = manual_restore
            self._reset_gamma_ramps = False
            print("Releasing lock")
        self.taskbar_icon.set_visual_state()
        self.writecfg()

    def _set_reset_gamma_ramps(self, event, manual_restore=True):
        if event:
            print("Menu command:", end=" ")
        print("Set calibration state to reset vcgt")
        if self.lock.locked():
            print("Waiting to acquire lock...")
        with self.lock:
            print("Acquired lock")
            setcfg("profile_loader.reset_gamma_ramps", 1)
            self._manual_restore = manual_restore
            self._reset_gamma_ramps = True
            print("Releasing lock")
        self.taskbar_icon.set_visual_state()
        self.writecfg()

    def _should_apply_profiles(
        self, enumerate_windows_and_processes=True, manual_override=2
    ):
        displaycal_running = self._is_displaycal_running()
        if displaycal_running:
            enumerate_windows_and_processes = False
        return (
            not self._is_other_running(enumerate_windows_and_processes)
            and (not displaycal_running or self._manual_restore == manual_override)
            and not self._skip
            and (
                "--force" in sys.argv[1:]
                or self._manual_restore
                or (
                    config.getcfg("profile.load_on_login")
                    and (
                        sys.platform != "win32"
                        or not calibration_management_isenabled()
                    )
                )
            )
        )

    def _toggle_fix_profile_associations(self, event, parent=None):
        if event:
            print("Menu command:", end=" ")
        print("Toggle fix profile associations", event.IsChecked())
        if event.IsChecked():
            dlg = FixProfileAssociationsDialog(self, parent)
            self.fix_profile_associations_dlg = dlg
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_CANCEL:
                print("Cancelled toggling fix profile associations")
                return False
        if self.lock.locked():
            print("Waiting to acquire lock...")
        with self.lock:
            print("Acquired lock")
            setcfg("profile_loader.fix_profile_associations", int(event.IsChecked()))
            if event.IsChecked():
                self._set_display_profiles()
            else:
                self._reset_display_profile_associations()
            self._manual_restore = True
            self.writecfg()
            print("Releasing lock")
        return event.IsChecked()

    def _set_exceptions(self):
        self._exceptions = {}
        self._exception_names = set()
        exceptions = config.getcfg("profile_loader.exceptions").strip()
        if exceptions:
            print("Exceptions:")
        for exception in exceptions.split(";"):
            exception = exception.split(":", 2)
            if len(exception) < 3:
                # Malformed, ignore
                continue
            for i in range(2):
                try:
                    exception[i] = int(exception[i])
                except Exception:
                    exception[i] = 0
            enabled, reset, path = exception
            key = path.lower()
            self._exceptions[key] = (enabled, reset, path)
            self._exception_names.add(os.path.basename(key))
            print(
                "Enabled=%s" % bool(enabled),
                "Action=%s" % (reset and "Reset" or "Disable"),
                path,
            )

    def _set_profile_associations(self, event):
        if event:
            print("Menu command:", end=" ")
        print("Set profile associations")
        dlg = ProfileAssociationsDialog(self)
        self.profile_associations_dlg = dlg
        dlg.Center()
        dlg.ShowModalThenDestroy()

    def writecfg(self):
        config.writecfg(
            module="apply-profiles",
            options=("argyll.dir", "profile.load_on_login", "profile_loader"),
        )


def get_display_name_edid(device, moninfo=None, index=None, include_adapter=False):
    edid = {}
    if device:
        display = str(device.DeviceString)
        try:
            edid = get_edid(device=device)
        except Exception:
            pass
    else:
        display = lang.getstr("unknown")
    display = edid.get("monitor_name", display)
    if moninfo:
        m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
        m_width = m_right - m_left
        m_height = m_bottom - m_top
        display = " @ ".join(
            [display, "%i, %i, %ix%i" % (m_left, m_top, m_width, m_height)]
        )
        if moninfo["Flags"] & MONITORINFOF_PRIMARY:
            display += " [PRIMARY]"
        if moninfo.get("_adapter") and include_adapter:
            display += " - %s" % moninfo["_adapter"].DeviceString
    if index is not None:
        display = "%i. %s" % (index + 1, display)
    return display, edid


def get_profile_desc(profile_path, include_basename_if_different=True):
    """Return profile description or path if not available"""
    if not profile_path:
        return ""
    try:
        profile = ICCP.ICCProfile(profile_path)
        profile_desc = profile.getDescription()
    except Exception as exception:
        if not isinstance(exception, IOError):
            exception = traceback.format_exc()
        print("Could not get description of profile %s:" % profile_path, exception)
    else:
        basename = os.path.basename(profile_path)
        name = os.path.splitext(basename)[0]
        if (
            basename != profile_desc
            and include_basename_if_different
            and name not in (profile_desc, safe_asciize(profile_desc))
        ):
            return "%s (%s)" % (profile_desc, basename)
        return profile_desc
    return profile_path


def main():
    unknown_option = None
    for arg in sys.argv[1:]:
        if (
            arg
            not in (
                "--debug",
                "-d",
                "--help",
                "--force",
                "-V",
                "--version",
                "--skip",
                "--test",
                "-t",
                "--verbose",
                "--verbose=1",
                "--verbose=2",
                "--verbose=3",
                "-v",
            )
            and (
                arg not in ("--oneshot", "--task", "--profile-associations")
                or sys.platform != "win32"
            )
            and (
                arg not in ("--verify", "--silent", "--error-dialog")
                or sys.platform == "win32"
            )
        ):
            unknown_option = arg
            break

    if "--help" in sys.argv[1:] or unknown_option:

        if unknown_option:
            print(
                "%s: unrecognized option `%s'"
                % (os.path.basename(sys.argv[0]), unknown_option)
            )
            if sys.platform == "win32":
                BaseApp._run_exitfuncs()
        print("Usage: %s [OPTION]..." % os.path.basename(sys.argv[0]))
        print("Apply profiles to configured display devices and load calibration")
        print("Version %s" % version)
        print("")
        print("Options:")
        print("  --help           Output this help text and exit")
        print("  --force          Force loading of calibration/profile (if it has been")
        print("                   disabled in %s.ini)" % appname)
        print("  --skip           Skip initial loading of calibration")
        if sys.platform == "win32":
            print("  --oneshot        Exit after loading calibration")
        else:
            print("  --verify         Verify if calibration was loaded correctly")
            print("  --silent         Do not show dialog box on error")
            print("  --error-dialog   Force dialog box on error")
        print("  -V, --version    Output version information and exit")
        if sys.platform == "win32":
            print("")
            import textwrap

            print(
                "Configuration options (%s):"
                % os.path.join(confighome, appbasename + "-apply-profiles.ini")
            )
            print("")
            for cfgname, cfgdefault in sorted(config.defaults.items()):
                if (
                    cfgname.startswith("profile_loader.")
                    or cfgname == "profile.load_on_login"
                ):
                    # Documentation
                    key = cfgname.split(".", 1)[1]
                    if key == "load_on_login":
                        cfgdoc = "Apply calibration state on login and preserve"
                    elif key == "buggy_video_drivers":
                        cfgdoc = (
                            "List of buggy video driver names (case "
                            "insensitive, delimiter: ';')"
                        )
                    elif key == "check_gamma_ramps":
                        cfgdoc = (
                            "Check if video card gamma table has "
                            "changed and reapply calibration state if so"
                        )
                    elif key == "exceptions":
                        cfgdoc = (
                            "List of exceptions (case "
                            "insensitive, delimiter: ';', format: "
                            "<enabled [0|1]>:<reset video card gamma table [0|1]:"
                            "<executable path>)"
                        )
                    elif key == "fix_profile_associations":
                        cfgdoc = "Automatically fix profile asociations"
                    elif key == "ignore_unchanged_gamma_ramps":
                        cfgdoc = (
                            "Ignore unchanged gamma table, i.e. reapply "
                            "calibration state even if no change (only "
                            "effective if profile_loader."
                            "track_other_processes = 0)"
                        )
                    elif key == "quantize_bits":
                        cfgdoc = "Quantize video card gamma table to <n> " "bits"
                    elif key == "reset_gamma_ramps":
                        cfgdoc = "Reset video card gamma table to linear"
                    elif key == "track_other_processes":
                        cfgdoc = (
                            "Reapply calibration state when other "
                            "processes launch or exit"
                        )
                    elif key == "tray_icon_animation_quality":
                        cfgdoc = "Tray icon animation quality, 0 = off"
                    else:
                        continue
                    # Name and valid values
                    valid = config.valid_values.get(cfgname)
                    if valid:
                        valid = "[%s]" % "|".join("%s" % v for v in valid)
                    else:
                        valid = config.valid_ranges.get(cfgname)
                        if valid:
                            valid = "[%s..%s]" % tuple(valid)
                        elif isinstance(cfgdefault, int):
                            # Boolean
                            valid = "[0|1]"
                        elif isinstance(cfgdefault, str):
                            # String
                            valid = "<string>"
                            cfgdefault = "'%s'" % cfgdefault
                        else:
                            valid = ""
                    print(cfgname.ljust(45, " "), valid)
                    cfgdoc += " [Default: %s]." % cfgdefault
                    for line in textwrap.fill(cfgdoc, 75).splitlines():
                        print(" " * 4 + line.rstrip())
    elif "-V" in sys.argv[1:] or "--version" in sys.argv[1:]:
        print("%s %s" % (os.path.basename(sys.argv[0]), version))
    else:
        if sys.platform == "win32":
            setup_profile_loader_task(exe, exedir, pydir)

        config.initcfg("apply-profiles")

        if (
            "--force" not in sys.argv[1:]
            and not config.getcfg("profile.load_on_login")
            and sys.platform != "win32"
        ):
            # Early exit incase profile loading has been disabled and isn't forced
            sys.exit()

        if "--error-dialog" in sys.argv[1:]:
            config.setcfg("profile_loader.error.show_msg", 1)
            config.writecfg(
                module="apply-profiles",
                options=("argyll.dir", "profile.load_on_login", "profile_loader"),
            )

        global lang
        from DisplayCAL import localization as lang

        lang.init()

        ProfileLoader()


if __name__ == "__main__":
    main()
