"""Task Scheduler interface.

Currently only implemented for Windows (Vista and up).
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

# Standard Library Imports
from __future__ import annotations

import codecs
import os
import re
import subprocess as sp
import sys
import tempfile
import time
import traceback
from typing import TYPE_CHECKING, Any

# Third Party Imports
import pywintypes
import winerror

# Local Imports
from DisplayCAL.config import (
    AUTOSTART,
    AUTOSTART_HOME,
    get_data_path,
)
from DisplayCAL.meta import DOMAIN
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.options import DEBUG
from DisplayCAL.safe_print import ENC
from DisplayCAL.util_os import is_superuser, which
from DisplayCAL.util_str import indent, universal_newlines
from DisplayCAL.util_win import run_as_admin

if TYPE_CHECKING:
    from collections.abc import Iterator

    from win32com.taskscheduler import ITaskScheduler


RUNLEVEL_HIGHESTAVAILABLE = "HighestAvailable"
RUNLEVEL_LEASTPRIVILEGE = "LeastPrivilege"

MULTIPLEINSTANCES_IGNORENEW = "IgnoreNew"
MULTIPLEINSTANCES_STOPEXISTING = "StopExisting"


class _Dict2XML(dict):
    """Base class for dictionary to XML conversion.

    Uses the dictionary keys as XML element names and the values as
    element values. Special keys 'cls_name' and 'cls_attr' are used to set
    the class name and attributes of the root element.
    """

    def __init__(self, *args, **kwargs) -> None:
        dict.__init__(self, *args, **kwargs)
        if "cls_name" not in self:
            self["cls_name"] = self.__class__.__name__
        if "cls_attr" not in self:
            self["cls_attr"] = ""

    def __str__(self) -> str:
        """Convert the dict to a string representation in XML format.

        Returns:
            str: The string representation of the dict in XML format.
        """
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
                cc = "".join(f"{part[0].upper()}{part[1:]}" for part in name.split("_"))
                if isinstance(value, (list, tuple)):
                    item = "\n".join([str(item) for item in value])
                else:
                    item = f"<{cc}>{value}</{cc}>"
            items.append(indent(item, "  "))
        return """<{cls_name}{cls_attr}>
{items}
</{cls_name}>""".format(
            cls_name=self["cls_name"],
            cls_attr=self["cls_attr"],
            items="\n".join(items),
        )


class _Trigger(_Dict2XML):
    """Base class for triggers.

    Args:
        interval (str): The interval between repetitions in ISO 8601 format.
        duration (str): The duration for which the trigger should repeat in
            ISO 8601 format.
        stop_at_duration_end (bool): Whether to stop the trigger at the end of
            the duration.
        enabled (bool): Whether the trigger is enabled.
    """

    def __init__(
        self,
        interval: None | str = None,
        duration: None | str = None,
        stop_at_duration_end: bool = False,
        enabled: bool = True,
    ) -> None:
        repetition = (
            interval
            and _Dict2XML(
                interval=interval,
                duration=duration,
                stop_at_duration_end=stop_at_duration_end,
                cls_name="Repetition",
            )
        ) or ""
        _Dict2XML.__init__(self, repetition=repetition, enabled=enabled)


class CalendarTrigger(_Trigger):
    """Trigger for a calendar event.

    Args:
        start_boundary (str): The start boundary in ISO 8601 format.
        days_interval (int): The interval in days for the trigger.
        weeks_interval (int): The interval in weeks for the trigger.
        days_of_week (list[int]): The days of the week for the trigger (1=
            Sunday, 2=Monday, ..., 7=Saturday).
        months (list[int]): The months for the trigger (1=January, 2=February,
            ..., 12=December).
        days_of_month (list[int]): The days of the month for the trigger (1-31).
    """

    def __init__(
        self,
        start_boundary: str = "2019-09-17T00:00:00",
        days_interval: int = 1,
        weeks_interval: int = 0,
        days_of_week: None | list[int] = None,
        months: None | list[int] = None,
        days_of_month: None | list[int] = None,
        **kwargs,
    ) -> None:
        _Trigger.__init__(self, **kwargs)
        self["start_boundary"] = start_boundary
        self["schedule_by_day"] = (
            days_interval
            and _Dict2XML(days_interval=days_interval, cls_name="ScheduleByDay")
        ) or ""
        self["schedule_by_week"] = (
            weeks_interval
            and _Dict2XML(
                days_of_week=_Dict2XML(items=days_of_week, cls_name="DaysOfWeek"),
                weeks_interval=weeks_interval,
                cls_name="ScheduleByWeek",
            )
        ) or ""
        self["schedule_by_month"] = (
            months
            and _Dict2XML(
                days_of_month=_Dict2XML(items=days_of_month, cls_name="DaysOfMonth"),
                months=_Dict2XML(items=months, cls_name="Months"),
                cls_name="ScheduleByMonth",
            )
        ) or ""


class LogonTrigger(_Trigger):
    """Trigger for when the user logs on."""


class ResumeFromSleepTrigger(_Trigger):
    """Trigger for when the system resumes from sleep."""

    def __init__(self, *args, **kwargs) -> None:
        _Trigger.__init__(self, *args, **kwargs)
        self["subscription"] = (
            """&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;"""
            """Select Path="System"&gt;*[System[Provider["""
            """@Name='Microsoft-Windows-Power-Troubleshooter'] and """
            """(Level=4 or Level=0) and """
            """(EventID=1)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;"""
        )
        self["cls_name"] = "EventTrigger"


class ExecAction(_Dict2XML):
    """Exec action.

    Args:
        cmd (str): The command to run.
        args (list[str]): The arguments to pass to the command. Defaults to None,
            which means no arguments.
    """

    def __init__(self, cmd: str, args: None | list[str] = None) -> None:
        # Filter any None values
        if args is not None:
            args = [arg for arg in args if arg is not None]
        _Dict2XML.__init__(
            self,
            command=cmd,
            arguments=(args and sp.list2cmdline(args)) or None,
            cls_name="Exec",
        )


class Task(_Dict2XML):
    """Task Scheduler task.

    Args:
        name (str): The name of the task.
        author (str): The author of the task.
        description (str): The description of the task.
        group_id (str): The group ID for the task.
        run_level (str): The run level for the task.
        multiple_instances_policy (str): The policy for multiple instances.
        disallow_start_if_on_batteries (bool): Whether to disallow starting
            the task if on batteries.
        stop_if_going_on_batteries (bool): Whether to stop the task if
            going on batteries.
        allow_hard_terminate (bool): Whether to allow hard termination of
            the task.
        start_when_available (bool): Whether to start the task when
            available.
        run_only_if_network_available (bool): Whether to run the task only
            if the network is available.
        duration (str): The duration for which the task should run.
        wait_timeout (str): The timeout for waiting for the task to finish.
        stop_on_idle_end (bool): Whether to stop the task when the system
            goes idle.
        restart_on_idle (bool): Whether to restart the task when the system
            goes idle.
        allow_start_on_demand (bool): Whether to allow starting the task on
            demand.
        enabled (bool): Whether the task is enabled.
        hidden (bool): Whether the task is hidden.
        run_only_if_idle (bool): Whether to run the task only if the system
            is idle.
        wake_to_run (bool): Whether to wake the system to run the task.
        execution_time_limit (str): The execution time limit for the task.
        priority (int): The priority of the task.
        triggers (list[_Trigger]): List of triggers for this task, e.g.:
            [LogonTrigger(), CalendarTrigger(), ResumeFromSleepTrigger()].
        actions (list[ExecAction]): List of actions for this task, e.g.:
            [ExecAction("program.exe", ["arg1", "arg2"])].
    """

    def __init__(
        self,
        name: str = "",
        author: str = "",
        description: str = "",
        group_id: str = "S-1-5-4",
        run_level: str = RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy: str = MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries: bool = False,
        stop_if_going_on_batteries: bool = False,
        allow_hard_terminate: bool = True,
        start_when_available: bool = False,
        run_only_if_network_available: bool = False,
        duration: None | str = None,
        wait_timeout: None | str = None,
        stop_on_idle_end: bool = False,
        restart_on_idle: bool = False,
        allow_start_on_demand: bool = True,
        enabled: bool = True,
        hidden: bool = False,
        run_only_if_idle: bool = False,
        wake_to_run: bool = False,
        execution_time_limit: str = "PT72H",
        priority: int = 5,
        triggers: None | list[_Trigger] = None,
        actions: None | list[ExecAction] = None,
    ) -> None:
        idle_settings = {
            "duration": duration,
            "wait_timeout": wait_timeout,
            "stop_on_idle_end": stop_on_idle_end,
            "restart_on_idle": restart_on_idle,
        }
        kwargs = {
            "allow_hard_terminate": allow_hard_terminate,
            "allow_start_on_demand": allow_start_on_demand,
            "disallow_start_if_on_batteries": disallow_start_if_on_batteries,
            "enabled": enabled,
            "execution_time_limit": execution_time_limit,
            "hidden": hidden,
            "multiple_instances_policy": multiple_instances_policy,
            "priority": priority,
            "run_only_if_idle": run_only_if_idle,
            "start_when_available": start_when_available,
            "stop_if_going_on_batteries": stop_if_going_on_batteries,
            "wake_to_run": wake_to_run,
        }
        settings = _Dict2XML(kwargs, cls_name="Settings")
        settings["idle_settings"] = _Dict2XML(idle_settings, cls_name="IdleSettings")

        kwargs = {}
        kwargs["registration_info"] = _Dict2XML(
            author=author,
            description=description,
            URI=f"\\{name}",
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

    def add_exec_action(self, cmd: str, args: None | list[str] = None) -> None:
        """Add an exec action to the task.

        Args:
            cmd (str): The command to run.
            args (list[str]): The arguments to pass to the command. Defaults to
                None, which means no arguments.
        """
        self["actions"]["items"].append(ExecAction(cmd, args))

    def add_logon_trigger(self, enabled: bool = True) -> None:
        """Add a logon trigger to the task.

        Args:
            enabled (bool): Whether the logon trigger is enabled. Defaults to
                True.
        """
        self["triggers"]["items"].append(LogonTrigger(enabled))

    def write_xml(self, xmlfilename: str) -> None:
        """Write the task to an XML file.

        Args:
            xmlfilename (str): The filename to write the XML to.
        """
        with open(xmlfilename, "wb") as xmlfile:
            xmlfile.write(codecs.BOM_UTF16_LE + str(self).encode("UTF-16-LE"))

    def __str__(self) -> str:
        """Convert the task to a string representation in XML format.

        Returns:
            str: The string representation of the task in XML format.
        """
        return universal_newlines(
            f'<?xml version="1.0" encoding="UTF-16"?>\n{super().__str__()}'
        ).replace("\n", "\r\n")


class TaskScheduler:
    """Task Scheduler interface.

    Currently only implemented for Windows (Vista and up).
    """

    def __init__(self) -> None:
        self.__ts = None
        self.stdout = b""
        self.lastreturncode = None

    @property
    def _ts(self) -> ITaskScheduler:
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

    def __contains__(self, name: str) -> bool:
        """Check if task with given name exists.

        Args:
            name (str): The name of the task to check.

        Returns:
            bool: True if the task exists, False otherwise.
        """
        return f"{name}.job" in self._ts.Enum()

    def __getitem__(self, name: str) -> Task:
        """Get existing task by name.

        Args:
            name (str): The name of the task to retrieve.

        Returns:
            Task: The task object.
        """
        return self._ts.Activate(name)

    def __iter__(self) -> Iterator:
        """Iterate over task names.

        Returns:
            Iterator: An iterator over task names.
        """
        return iter(job[:-4] for job in self._ts.Enum())

    def create_task(
        self,
        name: str,
        author: str = "",
        description: str = "",
        group_id: str = "S-1-5-4",
        run_level: str = RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy: str = MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries: bool = False,
        stop_if_going_on_batteries: bool = False,
        allow_hard_terminate: bool = True,
        start_when_available: bool = False,
        run_only_if_network_available: bool = False,
        duration: None | str = None,
        wait_timeout: None | int = None,
        stop_on_idle_end: bool = False,
        restart_on_idle: bool = False,
        allow_start_on_demand: bool = True,
        enabled: bool = True,
        hidden: bool = False,
        run_only_if_idle: bool = False,
        wake_to_run: bool = False,
        execution_time_limit: str = "PT72H",
        priority: int = 5,
        triggers: None | list[_Trigger] = None,
        actions: None | list[ExecAction] = None,
        replace_existing: bool = False,
        elevated: bool = False,
        echo: bool = False,
    ) -> bool:
        """Create a new task.

        If replace_existing evaluates to True, delete any existing task with
        same name first, otherwise raise KeyError.

        Args:
            name (str): The name of the task.
            author (str): The author of the task.
            description (str): The description of the task.
            group_id (str): The group ID for the task.
            run_level (str): The run level for the task.
            multiple_instances_policy (str): The policy for multiple instances.
            disallow_start_if_on_batteries (bool): Whether to disallow starting
                the task if on batteries.
            stop_if_going_on_batteries (bool): Whether to stop the task if
                going on batteries.
            allow_hard_terminate (bool): Whether to allow hard termination of
                the task.
            start_when_available (bool): Whether to start the task when
                available.
            run_only_if_network_available (bool): Whether to run the task only
                if the network is available.
            duration (str): The duration for which the task should run.
            wait_timeout (str): The timeout for waiting for the task to finish.
            stop_on_idle_end (bool): Whether to stop the task when the system
                goes idle.
            restart_on_idle (bool): Whether to restart the task when the system
                goes idle.
            allow_start_on_demand (bool): Whether to allow starting the task on
                demand.
            enabled (bool): Whether the task is enabled.
            hidden (bool): Whether the task is hidden.
            run_only_if_idle (bool): Whether to run the task only if the system
                is idle.
            wake_to_run (bool): Whether to wake the system to run the task.
            execution_time_limit (str): The execution time limit for the task.
            priority (int): The priority of the task.
            triggers (list[Trigger]): List of triggers for this task, e.g.:
                [LogonTrigger(), CalendarTrigger(), ResumeFromSleepTrigger()].
            actions (list[Action]): List of actions for this task, e.g.:
                [ExecAction("program.exe", ["arg1", "arg2"])].
            replace_existing (bool): If True, replace an existing task with same
                name, otherwise raise KeyError if it exists already.
            elevated (bool): If True, run command with elevated privileges,
                otherwise not. Note that this requires administrative privileges
                and will prompt for elevation if necessary.
            echo (bool): If True, print command
                output to stdout, otherwise suppress it.

        Raises:
            KeyError: If replace_existing is False and a task with the same
                name already exists.
            pywintypes.error: If there is an error while creating the task.
            OSError: If there is an error while writing the XML file or removing
                temporary files.

        Returns:
            bool: True if the task was created successfully, False otherwise.
        """
        kwargs = {
            "name": name,
            "author": author,
            "description": description,
            "group_id": group_id,
            "run_level": run_level,
            "multiple_instances_policy": multiple_instances_policy,
            "disallow_start_if_on_batteries": disallow_start_if_on_batteries,
            "stop_if_going_on_batteries": stop_if_going_on_batteries,
            "allow_hard_terminate": allow_hard_terminate,
            "start_when_available": start_when_available,
            "run_only_if_network_available": run_only_if_network_available,
            "duration": duration,
            "wait_timeout": wait_timeout,
            "stop_on_idle_end": stop_on_idle_end,
            "restart_on_idle": restart_on_idle,
            "allow_start_on_demand": allow_start_on_demand,
            "enabled": enabled,
            "hidden": hidden,
            "run_only_if_idle": run_only_if_idle,
            "wake_to_run": wake_to_run,
            "execution_time_limit": execution_time_limit,
            "priority": priority,
            "triggers": triggers,
            "actions": actions,
        }
        if not replace_existing and name in self:
            raise KeyError(f"The task {name} already exists!")

        tempdir = tempfile.mkdtemp(prefix=f"{APPNAME}-")
        task = Task(**kwargs)
        xmlfilename = os.path.join(tempdir, f"{name}.xml")
        task.write_xml(xmlfilename)
        args = ["/Create", "/TN", name, "/XML", xmlfilename]
        if replace_existing:
            args.append("/F")
        try:
            return self._schtasks(args, elevated, echo)
        finally:
            os.remove(xmlfilename)
            os.rmdir(tempdir)

    def create_logon_task(
        self,
        name: str,
        cmd: str,
        args: None | list[str] = None,
        author: str = "",
        description: str = "",
        group_id: str = "S-1-5-4",
        run_level: str = RUNLEVEL_LEASTPRIVILEGE,
        multiple_instances_policy: str = MULTIPLEINSTANCES_IGNORENEW,
        disallow_start_if_on_batteries: bool = False,
        stop_if_going_on_batteries: bool = False,
        allow_hard_terminate: bool = True,
        start_when_available: bool = False,
        run_only_if_network_available: bool = False,
        duration: None | str = None,
        wait_timeout: None | str = None,
        stop_on_idle_end: bool = False,
        restart_on_idle: bool = False,
        allow_start_on_demand: bool = True,
        enabled: bool = True,
        hidden: bool = False,
        run_only_if_idle: bool = False,
        wake_to_run: bool = False,
        execution_time_limit: str = "PT72H",
        priority: int = 5,
        replace_existing: bool = False,
        elevated: bool = False,
        echo: bool = False,
    ) -> Task:
        """Create a new task to be run under the current user account at logon.

        Args:
            name (str): The name of the task.
            cmd (str): The command to run.
            args (list[str]): The arguments to pass to the command.
            author (str): The author of the task.
            description (str): The description of the task.
            group_id (str): The group ID for the task.
            run_level (str): The run level for the task.
            multiple_instances_policy (str): The policy for multiple instances.
            disallow_start_if_on_batteries (bool): Whether to disallow starting
                the task if on batteries.
            stop_if_going_on_batteries (bool): Whether to stop the task if
                going on batteries.
            allow_hard_terminate (bool): Whether to allow hard termination of
                the task.
            start_when_available (bool): Whether to start the task when
                available.
            run_only_if_network_available (bool): Whether to run the task only
                if the network is available.
            duration (None | str): The duration for which the task should run.
            wait_timeout (str): The timeout for waiting for the task to finish.
            stop_on_idle_end (bool): Whether to stop the task when the system
                goes idle.
            restart_on_idle (bool): Whether to restart the task when the system
                goes idle.
            allow_start_on_demand (bool): Whether to allow starting the task on
                demand.
            enabled (bool): Whether the task is enabled.
            hidden (bool): Whether the task is hidden.
            run_only_if_idle (bool): Whether to run the task only if the system
                is idle.
            wake_to_run (bool): Whether to wake the system to run the task.
            execution_time_limit (str): The execution time limit for the task.
            priority (int): The priority of the task.
            replace_existing (bool): Whether to replace an existing task with
                the same name.
            elevated (bool): Whether to run the command with elevated
                privileges.
            echo (bool): Whether to print the command output to stdout.

        Returns:
            Task: The created task object.
        """
        kwargs = {
            "actions": [ExecAction(cmd, args)],
            "allow_hard_terminate": allow_hard_terminate,
            "allow_start_on_demand": allow_start_on_demand,
            "author": author,
            "description": description,
            "disallow_start_if_on_batteries": disallow_start_if_on_batteries,
            "duration": duration,
            "echo": echo,
            "elevated": elevated,
            "enabled": enabled,
            "execution_time_limit": execution_time_limit,
            "group_id": group_id,
            "hidden": hidden,
            "multiple_instances_policy": multiple_instances_policy,
            "name": name,
            "priority": priority,
            "replace_existing": replace_existing,
            "restart_on_idle": restart_on_idle,
            "run_level": run_level,
            "run_only_if_idle": run_only_if_idle,
            "run_only_if_network_available": run_only_if_network_available,
            "start_when_available": start_when_available,
            "stop_if_going_on_batteries": stop_if_going_on_batteries,
            "stop_on_idle_end": stop_on_idle_end,
            "triggers": [LogonTrigger()],
            "wait_timeout": wait_timeout,
            "wake_to_run": wake_to_run,
        }
        return self.create_task(**kwargs)

    def delete(self, name: str) -> None:
        """Delete existing task.

        Args:
            name (str): The name of the task to delete.
        """
        self._ts.Delete(name)

    def disable(self, name: str, echo: bool = False) -> None:
        """Disable (deactivate) existing task.

        Args:
            name (str): The name of the task to disable.
            echo (bool): Whether to print the command output to stdout.
        """
        self._schtasks(["/Change", "/TN", name, "/DISABLE"], echo=echo)

    def enable(self, name: str, echo: bool = False) -> None:
        """Enable (activate) existing task.

        Args:
            name (str): The name of the task to enable.
            echo (bool): Whether to print the command output to stdout.
        """
        self._schtasks(["/Change", "/TN", name, "/ENABLE"], echo=echo)

    def get(self, name: str, default: None | Any = None) -> None | Task:  # noqa: ANN401
        """Get existing task.

        Args:
            name (str): The name of the task to retrieve.
            default (None | Any): The value to return if the task does not
                exist.

        Returns:
            None | Task: The task object if it exists, otherwise the default
                value.
        """
        if name in self:
            return self[name]
        return default

    def get_exit_code(self, task: Task) -> tuple[int, int]:
        """Shorthand for task.GetExitCode().

        Return a 2-tuple exitcode, startup_error_code.

        Call win32api.FormatMessage() on either value to get a readable message

        Returns:
            tuple[int, int]: A tuple containing the exit code and startup error
                code of the task.
        """
        return task.GetExitCode()

    def items(self) -> list[tuple[str, Task]]:
        """Iterate over existing tasks and their names.

        Returns:
            list[tuple[str, Task]]: A list of tuples containing task names and
                their corresponding Task objects.
        """
        return list(zip(self, self.tasks()))

    def itertasks(self) -> Iterator[Task]:
        """Iterate over existing tasks.

        Returns:
            Iterator[Task]: An iterator over Task objects representing existing
                tasks.
        """
        return map(self.get, self)

    def run(self, name: str, elevated: bool = False, echo: bool = False) -> bool:
        """Run existing task.

        Args:
            name (str): The name of the task to run.
            elevated (bool): Whether to run the command with elevated privileges.
            echo (bool): Whether to print the command output to stdout.

        Returns:
            bool: True if the task was successfully run, False otherwise.
        """
        return self._schtasks(["/Run", "/TN", name], elevated, echo)

    def has_task(self, name: str) -> bool:
        """Same as name in self.

        Args:
            name (str): The name of the task to check.

        Returns:
            bool: True if the task exists, False otherwise.
        """
        return name in self

    def query_task(self, name: str, echo: bool = False) -> bool:
        """Query task.

        Args:
            name (str): The name of the task to query.
            echo (bool, optional): Whether to print the command output to
                stdout. Default is False.

        Returns:
            bool: True if the task exists, False otherwise.
        """
        return self._schtasks(["/Query", "/TN", name], False, echo)

    def _schtasks(
        self, args: list[str], elevated: bool = False, echo: bool = False
    ) -> bool:
        """Run schtasks.exe with the given arguments.

        Args:
            args (list[str]): The arguments to pass to schtasks.exe.
            elevated (bool): Whether to run the command with elevated privileges.
            echo (bool): Whether to print the command output to stdout.

        Returns:
            bool: True if the command was successful, False otherwise.
        """
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
                self.stdout = b""
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
            self.stdout, _ = p.communicate()
            if echo:
                print(str(self.stdout, encoding=ENC, errors="replace"))
            self.lastreturncode = p.returncode
        return self.lastreturncode == 0

    def tasks(self) -> list[Task]:
        """Get existing tasks.

        Returns:
            list[Task]: A list of Task objects representing existing tasks.
        """
        return list(map(self.get, self))


def setup_profile_loader_task(
    exe: str, exedir: str, pydir: str, force: bool = False
) -> None:
    """Setup profile loader task for Windows.

    Args:
        exe (str): Path to the executable.
        exedir (str): Directory of the executable.
        pydir (str): Directory of the Python installation.
        force (bool): Force creation of the task even if it already exists.
    """
    print("setup_profile_loader_task start")
    if sys.getwindowsversion() < (6,):
        print("setup_profile_loader_task end 1")
        return

    taskname = f"{APPNAME} Profile Loader Launcher"

    try:
        ts = TaskScheduler()
    except Exception as exception:
        print("Warning - could not access task scheduler:", exception)
        print("setup_profile_loader_task end 2")
        return

    if "--task" not in sys.argv[1:] and (force or is_superuser()) and (force or not ts.query_task(taskname)):
        # Check if our task exists, and if it does not, create it.
        # (requires admin privileges)
        print(f"Trying to create task {taskname}...")
        # Note that we use a stub so the task cannot be accidentally
        # stopped (the stub launches the actual profile loader and
        # then immediately exits)
        loader_args = []
        if os.path.basename(exe).lower() in ("python.exe", "pythonw.exe"):
            cmd = os.path.join(exedir, "pythonw.exe")
            pyw = os.path.normpath(
                os.path.join(pydir, "..", f"{APPNAME}-apply-profiles.pyw")
            )
            script = get_data_path(
                "/".join(["scripts", f"{APPNAME}-apply-profiles-launcher"])
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
                            f"http://{DOMAIN}/0install/{APPNAME}.xml",
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
            cmd = os.path.join(pydir, f"{APPNAME}-apply-profiles-launcher.exe")
        # Start at login, restart when resuming from sleep,
        # restart daily at 04:00
        triggers = [
            LogonTrigger(),
            ResumeFromSleepTrigger(),
        ]
        daily = CalendarTrigger(
            start_boundary=time.strftime("%Y-%m-%dT04:00:00"),
            days_interval=1,
        )
        actions = [ExecAction(cmd, loader_args)]
        try:
            # Create the main task
            created = ts.create_task(
                taskname,
                "Open Source Developer, Florian Höch",
                "This task launches the profile "
                "loader with the applicable "
                "privileges for logged in users",
                multiple_instances_policy=MULTIPLEINSTANCES_IGNORENEW,
                replace_existing=True,
                triggers=triggers,
                actions=actions,
            )
            # Create the supplementary task
            created = ts.create_task(
                f"{taskname} - Daily Restart",
                "Open Source Developer, Florian Höch",
                "This task restarts the profile "
                "loader with the applicable "
                "privileges for logged in users",
                multiple_instances_policy=MULTIPLEINSTANCES_IGNORENEW,
                replace_existing=True,
                triggers=[daily],
                actions=actions,
            )
        except Exception as exception:
            if DEBUG:
                exception = traceback.format_exc()
            print(
                f"Warning - Could not create task {taskname}:",
                exception,
            )
            if ts.stdout:
                print(str(ts.stdout, encoding=ENC, errors="replace"))
        else:
            print(str(ts.stdout, encoding=ENC, errors="replace"))
            if created:
                # Remove autostart entries, if any
                name = f"{APPNAME} Profile Loader"
                entries = []
                if AUTOSTART:
                    entries.append(os.path.join(AUTOSTART, f"{name}.lnk"))
                if AUTOSTART_HOME:
                    entries.append(os.path.join(AUTOSTART_HOME, f"{name}.lnk"))
                for entry in entries:
                    if os.path.isfile(entry):
                        print("Removing", entry)
                        try:
                            os.remove(entry)
                        except OSError as exception:
                            print(exception)

    from DisplayCAL.util_win import win_ver

    pname, _, _, build_str = win_ver()
    is_win10_or_later = "Windows 10" in pname or "Windows 11" in pname
    if not is_win10_or_later and build_str:
        try:
            bnum = int(build_str.split()[1].split(".")[0])
            if bnum >= 10240:
                is_win10_or_later = True
        except Exception:
            pass

    if not is_win10_or_later:
        print("setup_profile_loader_task end 3")
        return

    # Disable Windows Calibration Loader.
    # This is absolutely REQUIRED under Win10 1903 to prevent
    # banding and not applying calibration twice
    ms_cal_loader = r"\Microsoft\Windows\WindowsColorSystem\Calibration Loader"
    try:
        ts.disable(ms_cal_loader)
    except Exception as exception:
        print(
            f"Warning - Could not disable task {ms_cal_loader!r}:",
            exception,
        )
        if ts.stdout:
            print(str(ts.stdout, encoding=ENC, errors="replace"))
    else:
        print(str(ts.stdout, encoding=ENC, errors="replace"))
    print("setup_profile_loader_task end 4")


if __name__ == "__main__":

    def print_task_attr(name: str, attr: Any, *args: list[Any]) -> None:  # noqa: ANN401
        """Print task attribute.

        Args:
            name (str): The name of the attribute.
            attr (Any): The attribute value.
            *args: Additional arguments to pass to the attribute if it is
                callable.
        """
        print(f"{name:18s}:", end=" ")
        if callable(attr):
            try:
                print(attr(*args))
            except pywintypes.com_error as exception:
                print(OSError(*exception.args))
            except TypeError as exception:
                print(exception)
        else:
            print(attr)

    ts = TaskScheduler()

    for taskname in ts:
        task = ts[taskname]
        print("=" * 79)
        print("{:18s}:".format("Task"), taskname)
        for name in dir(task):
            if name == "GetRunTimes":
                continue
            attr = getattr(task, name)
            if name.startswith("Get"):
                if name in ("GetTrigger", "GetTriggerString"):
                    for i in range(task.GetTriggerCount()):
                        print_task_attr(f"{name[3:]}({i:d})", attr, i)
                else:
                    print_task_attr(name[3:], attr)
