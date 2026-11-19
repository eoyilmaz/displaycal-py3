import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_execaction_filters_none_values_in_args_and_will_not_raise_errors():
    """ExecAction will filter any None values in the args list and will not raise any errors."""
    from DisplayCAL.taskscheduler import ExecAction

    ea = ExecAction(cmd="", args=[None])  # This should not raise any errors.
    ea_no_args = ExecAction(cmd="")  # Default args=None should not raise TypeError.
    assert ea["arguments"] is None
    assert ea_no_args["arguments"] is None


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_task_str_returns_str():
    """Task.__str__() should return a str in Python 3, not bytes."""
    from DisplayCAL.taskscheduler import Task

    task = Task(name="TestTask", author="TestAuthor")
    result = str(task)
    assert isinstance(result, str)
    assert '<?xml version="1.0" encoding="UTF-16"?>' in result
    assert "<Task" in result
    assert "<Author>TestAuthor</Author>" in result


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_task_write_xml(tmp_path):
    """Task.write_xml() should write valid UTF-16 XML with BOM."""
    import codecs
    from DisplayCAL.taskscheduler import Task

    task = Task(name="TestTask", author="TestAuthor")
    xml_file = str(tmp_path / "task.xml")
    task.write_xml(xml_file)

    with open(xml_file, "rb") as f:
        content = f.read()

    assert content.startswith(codecs.BOM_UTF16_LE)
    decoded = content.decode("UTF-16")
    assert "<Author>TestAuthor</Author>" in decoded


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_create_task_passes_force_flag_on_replace_existing(monkeypatch):
    """create_task should pass /F flag when replace_existing=True."""
    from DisplayCAL.taskscheduler import TaskScheduler

    ts = TaskScheduler()
    captured_args = []

    def mock_schtasks(args, elevated=False, echo=False):
        captured_args.extend(args)
        return True

    monkeypatch.setattr(ts, "_schtasks", mock_schtasks)
    monkeypatch.setattr(ts, "__contains__", lambda self, name: False)

    ts.create_task("TestTask", replace_existing=True)
    assert "/F" in captured_args

    captured_args.clear()
    ts.create_task("TestTask", replace_existing=False)
    assert "/F" not in captured_args


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_setup_profile_loader_task_imports_without_gui():
    """setup_profile_loader_task must be importable without GUI/wx libraries."""
    from DisplayCAL.taskscheduler import setup_profile_loader_task

    assert callable(setup_profile_loader_task)


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_profile_loader_setup_task_args_recognized(monkeypatch):
    """Profile loader CLI arguments for task setup and calibration management should be recognized."""
    pytest.importorskip("wx")
    from DisplayCAL.profile_loader import filter_unknown_args

    for flag in ("--setup-task", "--disable-calibration-management", "--enable-calibration-management"):
        monkeypatch.setattr(sys, "argv", ["DisplayCAL-apply-profiles", flag])
        assert filter_unknown_args() is None



