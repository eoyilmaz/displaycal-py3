# -*- coding: utf-8 -*-
"""
Task Scheduler interface. Currently only implemented for Windows (Vista and up).
The implementation is currently minimal and incomplete when it comes to
creating tasks (all tasks are created for the 'INTERACTIVE' group and with
only logon triggers and exec actions available).

Note that most of the functionality requires administrative privileges.

Has a dict-like interface to query existing tasks.

>>> ts = TaskScheduler()

Check if task "name" exists:
>>> "name" in ts
or
>>> ts.has_task("name")

Get existing task "name":
>>> task = ts["name"]
or
>>> ts.get("name")

Run task:
>>> task.Run()
or
>>> ts.run("name")

Get task exit and startup error codes:
>>> exitcode, startup_error_code = task.GetExitCode()
or
>>> exitcode, startup_error_code = ts.get_exit_code(task)

Create a new task to be run under the current user account at logon:
>>> task = ts.create("name", "program.exe", ["arg1", "arg2", "argn"])

"""

import codecs
import os
import subprocess as sp
import sys
import tempfile

import pywintypes
import winerror

from DisplayCAL.meta import name as appname
from DisplayCAL.safe_print import enc
from DisplayCAL.util_os import getenvu
from DisplayCAL.util_str import indent, universal_newlines
from DisplayCAL.util_win import run_as_admin


RUNLEVEL_HIGHESTAVAILABLE = "HighestAvailable"
RUNLEVEL_LEASTPRIVILEGE = "LeastPrivilege"

MULTIPLEINSTANCES_IGNORENEW = "IgnoreNew"
MULTIPLEINSTANCES_STOPEXISTING = "StopExisting"


class _Dict2XML(dict):
    # Subclass this

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        if "cls_name" not in self:
            self["cls_name"] = self.__class__.__name__
        if "cls_attr" not in self:
            self["cls_attr"] = ""

    def __str__(self):
        items = []
        for name in self:
            value = self[name]
            if isinstance(value, bool):
                value = str(value).lower()
            elif name in ("cls_name", "cls_attr") or not value:
                continue
            if isinstance(value, _Dict2XML):
                item = str(value)
            else:
                cc = "".join(part[0].upper() + part[1:] for part in name.split("_"))
                if isinstance(value, (list, tuple)):
                    item = "\n".join([str(item) for item in value])
                else:
                    item = "<%(cc)s>%(value)s</%(cc)s>" % {"cc": cc, "value": value}
            items.append(indent(item, "  "))
        return """<%(cls_name)s%(cls_attr)s>
%(items)s
</%(cls_name)s>""" % {
            "cls_name": self["cls_name"],
            "cls_attr": self["cls_attr"],
            "items": "\n".join(items),
        }


class _Trigger(_Dict2XML):

    # Subclass this

    def __init__(
        self, interval=None, duration=None, stop_at_duration_end=False, enabled=True
    ):
        repetition = (
            interval
            and _Dict2XML(
                interval=interval,
                duration=duration,
                stop_at_duration_end=stop_at_duration_end,
                cls_name="Repetition",
            )
            or ""
        )
        _Dict2XML.__init__(self, repetition=repetition, enabled=enabled)


class CalendarTrigger(_Trigger):
    def __init__(
        self,
        start_boundary="2019-09-17T00:00:00",
        days_interval=1,
        weeks_interval=0,
        days_of_week=None,
        months=None,
        days_of_month=None,
        **kwargs
    ):
        _Trigger.__init__(self, **kwargs)
        self["start_boundary"] = start_boundary
        self["schedule_by_day"] = (
            days_interval
            and _Dict2XML(days_interval=days_interval, cls_name="ScheduleByDay")
            or ""
        )
        self["schedule_by_week"] = (
            weeks_interval
            and _Dict2XML(
                days_of_week=_Dict2XML(items=days_of_week, cls_name="DaysOfWeek"),
                weeks_interval=weeks_interval,
                cls_name="ScheduleByWeek",
            )
            or ""
        )
        self["schedule_by_month"] = (
            months
            and _Dict2XML(
                days_of_month=_Dict2XML(items=days_of_month, cls_name="DaysOfMonth"),
                months=_Dict2XML(items=months, cls_name="Months"),
                cls_name="ScheduleByMonth",
            )
            or ""
        )


class LogonTrigger(_Trigger):

    pass


class ResumeFromSleepTrigger(_Trigger):
    def __init__(self, *args, **kwargs):
        _Trigger.__init__(self, *args, **kwargs)
        self["subscription"] = (
            """&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and (Level=4 or Level=0) and (EventID=1)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;"""
        )
        self["cls_name"] = "EventTrigger"


class ExecAction(_Dict2XML):
    def __init__(self, cmd, args=None):
        # Filter any None values
        args = [arg for arg in args if arg is not None]
        _Dict2XML.__init__(
            self,
            command=cmd,
            arguments=args and sp.list2cmdline(args) or None,
            cls_name="Exec",
        )


class Task(_Dict2XML):
    def __init__(
        self,
        name="",
        author="",
        description="",
        group_id="S-1-5-4",
        run_level=RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy=MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries=False,
        stop_if_going_on_batteries=False,
        allow_hard_terminate=True,
        start_when_available=False,
        run_only_if_network_available=False,
        duration=None,
        wait_timeout=None,
        stop_on_idle_end=False,
        restart_on_idle=False,
        allow_start_on_demand=True,
        enabled=True,
        hidden=False,
        run_only_if_idle=False,
        wake_to_run=False,
        execution_time_limit="PT72H",
        priority=5,
        triggers=None,
        actions=None,
    ):
        kwargs = locals()
        idle_keys = ("duration", "wait_timeout", "stop_on_idle_end", "restart_on_idle")
        idle_settings = dict()
        for key in idle_keys:
            idle_settings[key] = kwargs[key]
        for key in (
            "self",
            "name",
            "author",
            "description",
            "group_id",
            "run_level",
            "triggers",
            "actions",
        ) + idle_keys:
            del kwargs[key]
        settings = _Dict2XML(kwargs, cls_name="Settings")
        settings["idle_settings"] = _Dict2XML(idle_settings, cls_name="IdleSettings")
        kwargs = dict()
        kwargs["registration_info"] = _Dict2XML(
            author=author,
            description=description,
            URI="\\" + name,
            cls_name="RegistrationInfo",
        )
        kwargs["triggers"] = _Dict2XML(items=triggers or [], cls_name="Triggers")
        kwargs["principals"] = _Dict2XML(
            items=[
                _Dict2XML(
                    group_id=group_id,
                    run_level=run_level,
                    cls_name="Principal",
                    cls_attr=' id="Author"',
                )
            ],
            cls_name="Principals",
        )
        kwargs["settings"] = settings
        kwargs["actions"] = _Dict2XML(
            items=actions or [], cls_name="Actions", cls_attr=' Context="Author"'
        )
        kwargs["cls_attr"] = (
            ' version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"'
        )
        _Dict2XML.__init__(self, kwargs)

    def add_exec_action(self, cmd, args=None):
        self["actions"]["items"].append(ExecAction(cmd, args))

    def add_logon_trigger(self, enabled=True):
        self["triggers"]["items"].append(LogonTrigger(enabled))

    def write_xml(self, xmlfilename):
        with open(xmlfilename, "wb") as xmlfile:
            xmlfile.write(codecs.BOM_UTF16_LE + str(self).encode())

    def __str__(self):
        return (
            universal_newlines(
                """<?xml version="1.0" encoding="UTF-16"?>
%s"""
                % str(self)
            )
            .replace("\n", "\r\n")
            .encode("UTF-16-LE")
        )


class TaskScheduler(object):
    def __init__(self):
        self.__ts = None
        self.stdout = ""
        self.lastreturncode = None

    @property
    def _ts(self):
        if not self.__ts:
            import pythoncom
            from win32com.taskscheduler.taskscheduler import (
                CLSID_CTaskScheduler,
                IID_ITaskScheduler,
            )

            self.__ts = pythoncom.CoCreateInstance(
                CLSID_CTaskScheduler,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                IID_ITaskScheduler,
            )
        return self.__ts

    def __contains__(self, name):
        return name + ".job" in self._ts.Enum()

    def __getitem__(self, name):
        return self._ts.Activate(name)

    def __iter__(self):
        return iter(job[:-4] for job in self._ts.Enum())

    def create_task(
        self,
        name,
        author="",
        description="",
        group_id="S-1-5-4",
        run_level=RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy=MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries=False,
        stop_if_going_on_batteries=False,
        allow_hard_terminate=True,
        start_when_available=False,
        run_only_if_network_available=False,
        duration=None,
        wait_timeout=None,
        stop_on_idle_end=False,
        restart_on_idle=False,
        allow_start_on_demand=True,
        enabled=True,
        hidden=False,
        run_only_if_idle=False,
        wake_to_run=False,
        execution_time_limit="PT72H",
        priority=5,
        triggers=None,
        actions=None,
        replace_existing=False,
        elevated=False,
        echo=False,
    ):
        """Create a new task.

        If replace_existing evaluates to True, delete any existing task with
        same name first, otherwise raise KeyError.

        """

        kwargs = locals()
        del kwargs["self"]
        del kwargs["replace_existing"]
        del kwargs["elevated"]
        del kwargs["echo"]

        if not replace_existing and name in self:
            raise KeyError("The task %s already exists" % name)

        tempdir = tempfile.mkdtemp(prefix=appname + "-")
        task = Task(**kwargs)
        xmlfilename = os.path.join(tempdir, name + ".xml")
        task.write_xml(xmlfilename)
        try:
            return self._schtasks(
                ["/Create", "/TN", name, "/XML", xmlfilename], elevated, echo
            )
        finally:
            os.remove(xmlfilename)
            os.rmdir(tempdir)

    def create_logon_task(
        self,
        name,
        cmd,
        args=None,
        author="",
        description="",
        group_id="S-1-5-4",
        run_level=RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy=MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries=False,
        stop_if_going_on_batteries=False,
        allow_hard_terminate=True,
        start_when_available=False,
        run_only_if_network_available=False,
        duration=None,
        wait_timeout=None,
        stop_on_idle_end=False,
        restart_on_idle=False,
        allow_start_on_demand=True,
        enabled=True,
        hidden=False,
        run_only_if_idle=False,
        wake_to_run=False,
        execution_time_limit="PT72H",
        priority=5,
        replace_existing=False,
        elevated=False,
        echo=False,
    ):

        kwargs = locals()
        del kwargs["self"]
        del kwargs["cmd"]
        del kwargs["args"]
        kwargs.update(
            {"triggers": [LogonTrigger()], "actions": [ExecAction(cmd, args)]}
        )
        return self.create_task(**kwargs)

    def delete(self, name):
        """Delete existing task"""
        self._ts.Delete(name)

    def disable(self, name, echo=False):
        """Disable (deactivate) existing task"""
        self._schtasks(["/Change", "/TN", name, "/DISABLE"], echo=echo)

    def enable(self, name, echo=False):
        """Enable (activate) existing task"""
        self._schtasks(["/Change", "/TN", name, "/ENABLE"], echo=echo)

    def get(self, name, default=None):
        """Get existing task"""
        if name in self:
            return self[name]
        return default

    def get_exit_code(self, task):
        """Shorthand for task.GetExitCode().

        Return a 2-tuple exitcode, startup_error_code.

        Call win32api.FormatMessage() on either value to get a readable message

        """
        return task.GetExitCode()

    def items(self):
        return list(zip(self, self.tasks()))

    def iteritems(self):
        return zip(self, self.itertasks())

    def itertasks(self):
        return map(self.get, self)

    def run(self, name, elevated=False, echo=False):
        """Run existing task"""
        return self._schtasks(["/Run", "/TN", name], elevated, echo)

    def has_task(self, name):
        """Same as name in self"""
        return name in self

    def query_task(self, name, echo=False):
        """Query task."""
        return self._schtasks(["/Query", "/TN", name], False, echo)

    def _schtasks(self, args, elevated=False, echo=False):
        if elevated:
            try:
                p = run_as_admin("schtasks.exe", args, close_process=False, show=False)
            except pywintypes.error as exception:
                if exception.args[0] == winerror.ERROR_CANCELLED:
                    self.lastreturncode = winerror.ERROR_CANCELLED
                else:
                    raise
            else:
                self.lastreturncode = int(p["hProcess"].handle == 0)
                p["hProcess"].Close()
            finally:
                self.stdout = ""
        else:
            args.insert(0, "schtasks.exe")
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = sp.SW_HIDE
            p = sp.Popen(
                [str(arg) for arg in args],
                stdin=sp.PIPE,
                stdout=sp.PIPE,
                stderr=sp.STDOUT,
                startupinfo=startupinfo,
            )
            self.stdout, stderr = p.communicate()
            if echo:
                print(str(self.stdout))
            self.lastreturncode = p.returncode
        return self.lastreturncode == 0

    def tasks(self):
        return list(map(self.get, self))


if __name__ == "__main__":

    def print_task_attr(name, attr, *args):
        print("%18s:" % name, end=" ")
        if callable(attr):
            try:
                print(attr(*args))
            except pywintypes.com_error as exception:
                print(WindowsError(*exception.args))
            except TypeError as exception:
                print(exception)
        else:
            print(attr)

    ts = TaskScheduler()

    for taskname in ts:
        task = ts[taskname]
        print("=" * 79)
        print("%18s:" % "Task", taskname)
        for name in dir(task):
            if name == "GetRunTimes":
                continue
            attr = getattr(task, name)
            if name.startswith("Get"):
                if name in ("GetTrigger", "GetTriggerString"):
                    for i in range(task.GetTriggerCount()):
                        print_task_attr(name[3:] + "(%i)" % i, attr, i)
                else:
                    print_task_attr(name[3:], attr)
