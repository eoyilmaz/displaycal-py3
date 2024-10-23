# -*- coding: utf-8 -*-
"""
Generic mock functions for unit-tests.

Use `check_call` as a context manager to mock calls and their return values as
well to check if the method was called (or not).
"""
from __future__ import annotations

import contextlib
from types import ModuleType
from typing import Any, Callable, Dict, Generator, List, Tuple, Type, overload

from _pytest.monkeypatch import MonkeyPatch
from mypy_extensions import KwArg, VarArg

Call = Tuple[Tuple[Any, ...], Dict[str, Any]]
CallList = List[Call]


@overload
@contextlib.contextmanager
def _mp_call(
    monkeypatch: MonkeyPatch,
    mock_class: Type[Any] | ModuleType,
    method: str,
    return_value: Any,
    as_property: bool,
) -> CallList:
    ...


@overload
@contextlib.contextmanager
def _mp_call(
    monkeypatch: MonkeyPatch,
    mock_class: str,
    method: Any,  # return value in this case
    return_value: bool,  # as_property in this case
) -> CallList:
    ...


def _mp_call(
    monkeypatch: MonkeyPatch,
    mock_class: Type[Any] | ModuleType | str,
    method: str | Any,
    return_value: Any,
    as_property: bool = False,
) -> CallList:
    """
    Mock a method in a class and record the calls to it.

    If the given return_value is an Exception, it will be raised. If not, the
    value will be returned from the mocked function/method.
    """
    calls: CallList = []

    def func_call(*a: Any, **k: Any) -> Any:
        """Mock the function call."""
        calls.append((a, k))
        if isinstance(return_value, Exception):
            # bug in pylint https://www.logilab.org/ticket/3207
            raise return_value  # pylint: disable-msg=raising-bad-type
        if callable(return_value):
            # Handle the case that a function was passed
            return return_value(*a, **k)
        return return_value

    # first case handles class + method, second one mock as str
    if as_property or (isinstance(mock_class, str) and return_value):
        callback: Callable[[VarArg(Any), KwArg(Any)], Any] | property = property(
            func_call
        )
    else:
        callback = func_call

    if isinstance(mock_class, str):
        return_value = method
        monkeypatch.setattr(mock_class, callback)
    else:
        monkeypatch.setattr(mock_class, method, callback)
    return calls


@contextlib.contextmanager
def check_call(  # pylint: disable=too-many-arguments
    mock_class: Type[Any] | ModuleType,
    method: str,
    return_value: Any = None,
    call_args_list: List[Tuple[Any, ...]] | None = None,
    call_kwargs_list: List[Dict[str, Any]] | None = None,
    call_count: int = 1,
    as_property: bool = False,
) -> Generator[CallList, None, None]:
    """Context manager for mocking and checking a call to a method.

    If called is greater 0, and call_args and call_kwargs are given, the context manager
    will check that the mocked method was called with those arguments. Also, it will
    assert that the mock was called exactly once.

    If called is False, it will assert that the mock was not called.

    If a return_value is given, the mock will return this value. One can pass an
    exception that will be raised by the mocked method instead of returning a value.
    If a Callable is passed, it will be called and its return value returned.
    """
    assert (call_args_list is not None and call_kwargs_list is not None) or (
        call_args_list is None and call_kwargs_list is None
    ), (
        "call_args and call_kwargs must be None or have a value " "(list/dict if empty)"
    )
    monkeypatch = MonkeyPatch()
    calls = _mp_call(monkeypatch, mock_class, method, return_value, as_property)
    try:
        yield calls
    finally:
        m_name = f"{mock_class.__name__}.{method}"
        monkeypatch.undo()
        assert_calls(call_count, call_args_list, call_kwargs_list, calls, m_name)


# Duplicate the code because overloading is a mess due to this bug:
# https://github.com/python/mypy/issues/11373
@contextlib.contextmanager
def check_call_str(  # pylint: disable=too-many-arguments
    mock_class: str,
    return_value: Any = None,
    call_args_list: List[Tuple[Any, ...]] | None = None,
    call_kwargs_list: List[Dict[str, Any]] | None = None,
    call_count: int = 1,
    as_property: bool = False,
) -> Generator[CallList, None, None]:
    """
    Context manager for mocking and checking a call to a method.

    See `check_call` documentation.
    """
    assert (call_args_list is not None and call_kwargs_list is not None) or (
        call_args_list is None and call_kwargs_list is None
    ), (
        "call_args and call_kwargs must be None or have a value " "(list/dict if empty)"
    )
    monkeypatch = MonkeyPatch()
    calls = _mp_call(monkeypatch, mock_class, return_value, as_property)
    yield calls
    m_name = mock_class
    monkeypatch.undo()
    assert_calls(call_count, call_args_list, call_kwargs_list, calls, m_name)


def assert_calls(
    call_count: int,
    call_args_list: List[Tuple[Any, ...]] | None,
    call_kwargs_list: List[Dict[str, Any]] | None,
    calls: CallList,
    m_name: str,
) -> None:
    """Check that the calls made to the mocked function are correct."""
    if call_count != -1:
        assert (
            len(calls) == call_count
        ), f"Expected {call_count} calls to {m_name} but got: {len(calls)}"
    if call_args_list and call_kwargs_list:
        for idx, call_args in enumerate(call_args_list):
            assert (
                call_args == calls[idx][0]
            ), f"Args to {m_name}: {call_args} expected: {call_args}"
        for idx, call_kwargs in enumerate(call_kwargs_list):
            assert (
                call_kwargs == calls[idx][1]
            ), f"Kwargs to {m_name}: {call_kwargs} expected: {call_kwargs}"
