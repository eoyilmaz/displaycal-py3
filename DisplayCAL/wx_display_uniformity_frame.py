"""Interactive display calibration UI."""

import os
import re
import sys
from time import strftime

from DisplayCAL import localization as lang
from DisplayCAL import report
from DisplayCAL.config import (
    get_display_number,
    get_display_rects,
    get_icon_bundle,
    get_verified_path,
    getbitmap,
    getcfg,
    setcfg,
)
from DisplayCAL.debughelpers import Error
from DisplayCAL.log import get_file_logger
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import VERSION_STRING as APPVERSION
from DisplayCAL.util_os import launch_file, waccess
from DisplayCAL.wx_addons import CustomEvent, wx
from DisplayCAL.wx_measure_frame import MeasureFrame
from DisplayCAL.wx_windows import (
    NAV_KEYCODES,
    NUMPAD_KEYCODES,
    PROCESSING_KEYCODES,
    BaseFrame,
    FlatShadedButton,
    wx_Panel,
)

BGCOLOUR = wx.Colour(0x33, 0x33, 0x33)


class FlatShadedNumberedButton(FlatShadedButton):
    """Flat shaded button with a number.

    Args:
        parent (wx.Window): The parent window for this button.
        id (int, optional): The identifier for the button. Defaults to
            wx.ID_ANY.
        bitmap (wx.Bitmap, optional): The bitmap to display on the button.
            Defaults to None.
        label (str, optional): The label for the button. Defaults to an empty
            string.
        pos (wx.Point, optional): The position of the button. Defaults to
            wx.DefaultPosition.
        size (wx.Size, optional): The size of the button. Defaults to
            wx.DefaultSize.
        style (int, optional): The style of the button. Defaults to
            wx.NO_BORDER.
        validator (wx.Validator, optional): The validator for the button.
            Defaults to wx.DefaultValidator.
        name (str, optional): The name of the button. Defaults to
            "gradientbutton".
        bgcolour (wx.Colour, optional): The background colour of the button.
            Defaults to None.
        fgcolour (wx.Colour, optional): The foreground colour of the button.
            Defaults to None.
        index (int, optional): The index of the button in the grid. Defaults to
            0.
    """

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,  # noqa: A002
        bitmap=None,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.NO_BORDER,
        validator=wx.DefaultValidator,
        name="gradientbutton",
        bgcolour=None,
        fgcolour=None,
        index=0,
    ):
        FlatShadedButton.__init__(
            self,
            parent,
            id,
            bitmap,
            label,
            pos,
            size,
            style,
            validator,
            name,
            bgcolour,
            fgcolour,
        )
        self.index = index

    def OnGainFocus(self, event):
        """Handle the focus gain event for the button.

        Args:
            event (wx.Event): The focus gain event triggered when the button
                gains focus.
        """
        self.TopLevelParent.index = self.index
        FlatShadedButton.OnGainFocus(self, event)


class DisplayUniformityFrame(BaseFrame):
    """Display uniformity measurement frame.

    Args:
        parent (wx.Window): The parent window for this frame.
        handler (callable, optional): A function to handle timer events.
            Defaults to None.
        keyhandler (callable, optional): A function to handle key events.
            Defaults to None.
        start_timer (bool, optional): Whether to start the timer on
            initialization. Defaults to True.
        rows (int, optional): Number of rows in the grid. Defaults to config
            value.
        cols (int, optional): Number of columns in the grid. Defaults to config
            value.
    """

    def __init__(
        self,
        parent=None,
        handler=None,
        keyhandler=None,
        start_timer=True,
        rows=None,
        cols=None,
    ):
        if not rows:
            rows = getcfg("uniformity.rows")
        if not cols:
            cols = getcfg("uniformity.cols")
        BaseFrame.__init__(
            self,
            parent,
            wx.ID_ANY,
            lang.getstr("report.uniformity"),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
            name="displayuniformityframe",
        )
        self.SetIcons(get_icon_bundle([256, 48, 32, 16], APPNAME))
        self.SetBackgroundColour(BGCOLOUR)
        self.sizer = wx.GridSizer(rows, cols, 0, 0)
        self.SetSizer(self.sizer)

        self.rows = rows
        self.cols = cols
        self.colors = (
            wx.WHITE,
            wx.Colour(192, 192, 192),
            wx.Colour(128, 128, 128),
            wx.Colour(64, 64, 64),
        )
        self.labels = {}
        self.panels = []
        self.buttons = []
        for index in range(rows * cols):
            panel = wx_Panel(self, style=wx.BORDER_SIMPLE)
            panel.SetBackgroundColour(BGCOLOUR)
            sizer = wx.BoxSizer(wx.VERTICAL)
            panel.SetSizer(sizer)
            self.panels.append(panel)
            button = FlatShadedNumberedButton(
                panel,
                label=lang.getstr("measure"),
                bitmap=getbitmap("theme/icons/10x10/record"),
                index=index,
            )
            button.Bind(wx.EVT_BUTTON, self.measure)
            self.buttons.append(button)
            label = wx.StaticText(panel)
            label.SetForegroundColour(wx.WHITE)
            self.labels[index] = label
            sizer.Add(label, 1, wx.ALIGN_CENTER)
            sizer.Add(
                button,
                0,
                wx.ALIGN_CENTER | wx.BOTTOM,
                # | wx.LEFT | wx.RIGHT,
                border=8,
            )
            self.sizer.Add(panel, 1, wx.EXPAND)
        self.disable_buttons()

        self.keyhandler = keyhandler
        self.id_to_keycode = {}
        if sys.platform == "darwin":
            # Use an accelerator table for tab, space, 0-9, A-Z, numpad,
            # navigation keys and processing keys
            keycodes = [wx.WXK_TAB, wx.WXK_SPACE]
            keycodes.extend(list(range(ord("0"), ord("9"))))
            keycodes.extend(list(range(ord("A"), ord("Z"))))
            keycodes.extend(NUMPAD_KEYCODES)
            keycodes.extend(NAV_KEYCODES)
            keycodes.extend(PROCESSING_KEYCODES)
            for keycode in keycodes:
                self.id_to_keycode[wx.Window.NewControlId()] = keycode
            accels = []
            for id_ in self.id_to_keycode:
                keycode = self.id_to_keycode[id_]
                self.Bind(wx.EVT_MENU, self.key_handler, id=id_)
                accels.append((wx.ACCEL_NORMAL, keycode, id_))
                if keycode == wx.WXK_TAB:
                    accels.append((wx.ACCEL_SHIFT, keycode, id_))
            self.SetAcceleratorTable(wx.AcceleratorTable(accels))
        else:
            self.Bind(wx.EVT_CHAR_HOOK, self.key_handler)

        # Event handlers
        self.Bind(wx.EVT_CLOSE, self.OnClose, self)
        self.Bind(wx.EVT_MOVE, self.OnMove, self)
        self.timer = wx.Timer(self)
        if handler:
            self.Bind(wx.EVT_TIMER, handler, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        # Final initialization steps
        self.logger = get_file_logger("uniformity")
        self._setup()

        self.Show()

        if start_timer:
            self.start_timer()

    def EndModal(self, returncode=wx.ID_OK):
        """End the modal state of the display uniformity frame.

        Args:
            returncode (int): The return code to indicate the result of the modal
                operation. Default is wx.ID_OK.

        Returns:
            int: The return code indicating the result of the modal operation.
        """
        return returncode

    def MakeModal(self, modal=False):
        """Make the display uniformity frame modal.

        Args:
            modal (bool): If True, make the frame modal; if False, make it
                non-modal.
        """

    def OnClose(self, event):
        """Handle the close event for the display uniformity frame.

        Args:
            event (wx.Event): The close event triggered when the frame is closed.
        """
        if not self.timer.IsRunning():
            self.Destroy()
        else:
            self.keepGoing = False

    def OnDestroy(self, event):
        """Handle the destruction of the display uniformity frame.

        Args:
            event (wx.Event): The destroy event triggered when the frame is closed.
        """
        self.stop_timer()
        del self.timer
        if not hasattr(wx.Window, "UnreserveControlId"):
            return 0
        for id_ in self.id_to_keycode:
            if id_ >= 0:
                continue
            try:
                wx.Window.UnreserveControlId(id_)
            except wx.wxAssertionError as exception:
                print(exception)
        return 0

    def OnMove(self, event):
        """Handle the move event for the display uniformity frame.

        Args:
            event (wx.Event): The move event triggered when the frame is moved.
        """

    def Pulse(self, msg=""):
        """Pulse the display uniformity frame with a message.

        Args:
            msg (str): The message to display during the pulse.
        """
        return self.keepGoing, False

    def Resume(self):
        """Resume the display uniformity frame."""
        self.keepGoing = True

    def Show(self, show=True):
        """Show or hide the display uniformity frame.

        Args:
            show (bool): If True, show the frame; if False, hide it.
        """
        if show:
            display_no = getcfg("display.number") - 1
            if display_no < 0 or display_no > wx.Display.GetCount() - 1:
                display_no = 0
            else:
                display_no = get_display_number(display_no)
            x, y, w, h = wx.Display(display_no).ClientArea
            # Place frame on correct display
            self.SetPosition((x, y))
            self.SetSize((w, h))
            self.disable_buttons()
            wx.CallAfter(self.Maximize)
        wx.Frame.Show(self, show)
        self.panels[0].SetFocus()

    def UpdateProgress(self, value, msg=""):
        """Update the progress of the display uniformity frame.

        Args:
            value (int): The progress value to update.
            msg (str): The message to display during the progress update.

        Returns:
            bool: True if the pulse was successful, False otherwise.
        """
        return self.Pulse(msg)

    def UpdatePulse(self, msg=""):
        """Update the pulse with a message.

        Args:
            msg (str): The message to display during the pulse.
        """
        return self.Pulse(msg)

    def disable_buttons(self):
        """Disable all buttons in the display uniformity frame."""
        self.enable_buttons(False)

    def enable_buttons(self, enable=True):
        """Enable or disable all buttons in the display uniformity frame.

        Args:
            enable (bool): If True, enable the buttons; if False, disable them.
        """
        for button in self.buttons:
            button.Enable(enable)

    def flush(self):
        """Flush the output stream."""

    get_display = MeasureFrame.__dict__["get_display"]

    def has_worker_subprocess(self):
        """Check if the worker subprocess exists.

        Returns:
            bool: True if the worker subprocess exists, False otherwise.
        """
        return bool(
            getattr(self, "worker", None) and getattr(self.worker, "subprocess", None)
        )

    def hide_cursor(self):
        """Hide the cursor and set it to a blank cursor."""
        cursor_id = wx.CURSOR_BLANK
        cursor = wx.StockCursor(cursor_id)
        self.SetCursor(cursor)
        for panel in self.panels:
            panel.SetCursor(cursor)
        for label in list(self.labels.values()):
            label.SetCursor(cursor)
        for button in self.buttons:
            button.SetCursor(cursor)

    def isatty(self):
        """Check if the standard output is a terminal.

        Returns:
            bool: True if the standard output is a terminal, False otherwise.
        """
        return True

    def key_handler(self, event):
        """Handle key events for the display uniformity frame.

        Args:
            event (wx.Event): The key event to handle.
        """
        keycode = None
        if event.GetEventType() in (
            wx.EVT_CHAR.typeId,
            wx.EVT_CHAR_HOOK.typeId,
            wx.EVT_KEY_DOWN.typeId,
        ):
            keycode = event.GetKeyCode()
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            keycode = self.id_to_keycode.get(event.GetId())
        if keycode == wx.WXK_TAB:
            self.global_navigate() or event.Skip()
        elif keycode >= 0:
            if self.has_worker_subprocess() and keycode < 256:
                if keycode == wx.WXK_ESCAPE or chr(keycode) == "Q":
                    # ESC or Q
                    self.worker.abort_subprocess()
                elif (
                    self.index > -1
                    and not self.is_measuring
                    and (
                        not isinstance(self.FindFocus(), wx.Control)
                        or keycode != wx.WXK_SPACE
                    )
                ):
                    # Any other key
                    self.measure(
                        CustomEvent(wx.EVT_BUTTON.typeId, self.buttons[self.index])
                    )
                else:
                    event.Skip()
            else:
                event.Skip()
        else:
            event.Skip()

    def measure(self, event=None):
        """Start measuring the uniformity grid.

        Args:
            event (wx.Event, optional): The event that triggered the
                measurement. Defaults to None.
        """
        if event:
            self.index = event.GetEventObject().index
            print(f"{APPNAME}: Uniformity grid index {self.index}")
            self.is_measuring = True
            self.results[self.index] = []
            self.labels[self.index].SetLabel("")
            self.hide_cursor()
            self.disable_buttons()
            self.buttons[self.index].Hide()
        self.panels[self.index].SetBackgroundColour(
            self.colors[len(self.results[self.index])]
        )
        self.panels[self.index].Refresh()
        self.panels[self.index].Update()
        print(
            f"{APPNAME}: About to measure uniformity grid index {self.index} "
            f"@{self.colors[len(self.results[self.index])].red / 2.55}%"
        )
        # Use a delay to allow for TFT lag
        wx.CallLater(200, self.safe_send, " ")

    def parse_txt(self, txt):
        """Parse the text output from the instrument.

        Args:
            txt (str): The text output from the instrument.
        """
        if not txt:
            return
        self.logger.info(f"{txt!r}")
        if "Setting up the instrument" in txt:
            self.Pulse(lang.getstr("instrument.initializing"))
        if "Spot read failed" in txt:
            self.last_error = txt
        if "Result is XYZ:" in txt:
            # Result is XYZ: d.dddddd d.dddddd d.dddddd, D50 Lab: d.dddddd d.dddddd d.dddddd  # noqa: E501
            #                           CCT = ddddK (Delta E d.dddddd)
            # Closest Planckian temperature = ddddK (Delta E d.dddddd)
            # Closest Daylight temperature  = ddddK (Delta E d.dddddd)
            XYZ = re.search(r"XYZ:\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", txt)
            self.results[self.index].append(
                {"XYZ": [float(value) for value in XYZ.groups()]}
            )
            self.last_error = None
        loci = {"t": "Daylight", "T": "Planckian"}
        for locus in list(loci.values()):
            if locus in txt:
                CT = re.search(
                    rf"Closest\s+{locus}\s+temperature\s+=\s+(\d+)K", txt, re.I
                )
                self.results[self.index][-1][f"C{locus[0]}T"] = int(CT.groups()[0])
        if "key to take a reading" not in txt or self.last_error:
            return
        print(f"{APPNAME}: Got 'key to take a reading'")
        if not self.is_measuring:
            self.enable_buttons()
            return
        if len(self.results[self.index]) < len(self.colors):
            # Take readings at 5 different brightness levels per swatch
            print(f"{APPNAME}: About to take next reading")
            self.measure()
        else:
            self.is_measuring = False
            self.show_cursor()
            self.enable_buttons()
            self.buttons[self.index].Show()
            self.buttons[self.index].SetFocus()
            self.buttons[self.index].SetBitmap(getbitmap("theme/icons/16x16/checkmark"))
            self.panels[self.index].SetBackgroundColour(BGCOLOUR)
            self.panels[self.index].Refresh()
            self.panels[self.index].Update()
            if len(self.results) == self.rows * self.cols:
                # All swatches have been measured, show results
                # Let the user choose a location for the results html
                display_no, geometry, client_area = self.get_display()
                # Translate from wx display index to Argyll display index
                geometry = f"{geometry[0]}, {geometry[1]}, {geometry[2]}x{geometry[3]}"
                for i, display in enumerate(getcfg("displays")):
                    if display.find(f"@ {geometry}") > -1:
                        print(f"Found display {display} at index {i}")
                        break
                display = display.replace(" [PRIMARY]", "")
                defaultFile = "Uniformity Check {} — {} — {}".format(
                    APPVERSION,
                    re.sub(r"[\\/:*?\"<>|]+", "_", display),
                    strftime("%Y-%m-%d %H-%M.html"),
                )
                defaultDir = get_verified_path(
                    None, os.path.join(getcfg("profile.save_path"), defaultFile)
                )[0]
                dlg = wx.FileDialog(
                    self,
                    lang.getstr("save_as"),
                    defaultDir,
                    defaultFile,
                    wildcard=lang.getstr("filetype.html") + "|*.html;*.htm",
                    style=wx.SAVE | wx.FD_OVERWRITE_PROMPT,
                )
                dlg.Center(wx.BOTH)
                result = dlg.ShowModal()
                if result == wx.ID_OK:
                    path = dlg.GetPath()
                    if not waccess(path, os.W_OK):
                        from DisplayCAL.worker import show_result_dialog

                        show_result_dialog(
                            Error(lang.getstr("error.access_denied.write", path)),
                            self,
                        )
                        return
                    save_path = os.path.splitext(path)[0] + ".html"
                    setcfg("last_filedialog_path", save_path)
                dlg.Destroy()
                if result != wx.ID_OK:
                    return
                locus = loci.get(getcfg("whitepoint.colortemp.locus"))
                try:
                    report.create(
                        save_path,
                        {
                            "${REPORT_VERSION}": APPVERSION,
                            "${DISPLAY}": display,
                            "${DATETIME}": strftime("%Y-%m-%d %H:%M:%S"),
                            "${ROWS}": str(self.rows),
                            "${COLS}": str(self.cols),
                            "${RESULTS}": str(self.results),
                            "${LOCUS}": locus,
                        },
                        getcfg("report.pack_js"),
                        "uniformity",
                    )
                except OSError as exception:
                    from DisplayCAL.worker import show_result_dialog

                    show_result_dialog(exception, self)
                else:
                    launch_file(save_path)
            if getcfg("uniformity.measure.continuous"):
                self.measure(event=Event(self.buttons[self.index]))

    def reset(self):
        """Reset the display uniformity frame to its initial state."""
        self._setup()
        for panel in self.panels:
            panel.SetBackgroundColour(BGCOLOUR)
        for button in self.buttons:
            button.SetBitmap(getbitmap("theme/icons/10x10/record"))
            button.Show()
        for index in self.labels:
            self.labels[index].SetLabel("")
            self.labels[index].GetContainingSizer().Layout()
        self.show_cursor()

    def _setup(self):
        self.logger.info("-" * 80)
        self.index = 0
        self.is_measuring = False
        self.keepGoing = True
        self.last_error = None
        self.results = {}
        self.display_rects = get_display_rects()

    def safe_send(self, data):
        """Safely send the data to the worker subprocess if it exists.

        Args:
            data (str): The data to send to the worker subprocess.
        """
        if self.has_worker_subprocess() and not self.worker.subprocess_abort:
            if not self.worker.instrument_on_screen:
                if not getattr(self, "wait_for_instrument_on_screen", False):
                    self.wait_for_instrument_on_screen = True
                    print(f"{APPNAME}: Waiting for instrument to be placed on screen")
                wx.CallLater(200, self.safe_send, data)
            else:
                self.wait_for_instrument_on_screen = False
                self.worker.safe_send(data)

    def show_cursor(self):
        """Show the cursor and reset it to the default arrow cursor."""
        cursor = wx.StockCursor(wx.CURSOR_ARROW)
        self.SetCursor(cursor)
        for panel in self.panels:
            panel.SetCursor(cursor)
        for label in list(self.labels.values()):
            label.SetCursor(cursor)
        for button in self.buttons:
            button.SetCursor(cursor)

    def start_timer(self, ms=50):
        """Start the timer with a specified interval in milliseconds.

        Args:
            ms (int): The interval in milliseconds for the timer. Default is 50 ms.
        """
        self.timer.Start(ms)

    def stop_timer(self):
        """Stop the timer."""
        self.timer.Stop()

    def write(self, txt):
        """Write text to the display uniformity frame."""
        wx.CallAfter(self.parse_txt, txt)


class Event:
    """Custom event class to handle events in the DisplayUniformityFrame.

    Args:
        evtobj (wx.Events): The event object associated with this event.
    """

    def __init__(self, evtobj):
        self.evtobj = evtobj

    def GetEventObject(self):
        """Return the event object.

        Returns:
            The event object associated with this event.
        """
        return self.evtobj
