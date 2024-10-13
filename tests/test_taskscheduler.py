# -*- coding: utf-8 -*-

import pytest
import sys


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_execaction_filters_none_values_in_args_and_will_not_raise_errors():
    """ExecAction will filter any None values in the args list and will not raise any errors."""
    from DisplayCAL.taskscheduler import ExecAction

    ea = ExecAction(cmd="", args=[None])  # This should not raise any errors.
