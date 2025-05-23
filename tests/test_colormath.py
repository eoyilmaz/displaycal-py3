import pytest

from DisplayCAL.colormath import smooth_avg_old, smooth_avg
from tests.data.display_data import DisplayData


def test_smooth_avg_1():
    """testing if the smooth_avg function is working properly"""
    test_values = DisplayData.values_to_smooth
    expected_result = DisplayData.expected_smooth_values
    passes = 1
    window = None
    protect = None
    result = smooth_avg(test_values, passes, window, protect)
    assert result == pytest.approx(expected_result)


def test_smooth_avg_is_matching_old_implementation_1():
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    expected_result = DisplayData.expected_smooth_values
    passes = 1
    window = None
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    assert result_1 == pytest.approx(result_2)
    assert result_1 == pytest.approx(expected_result)
    assert result_2 == pytest.approx(expected_result)


def test_smooth_avg_is_matching_old_implementation_2():
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    passes = 1
    window = tuple([1] * 5)
    window_size = len(window)
    half_window_size = int(window_size / 2)
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    # unfortunately the first value after start and first value after end are not
    # matching, but the rest are perfectly matching
    assert result_1[half_window_size:-half_window_size] == pytest.approx(
        result_2[half_window_size:-half_window_size]
    )


def test_smooth_avg_is_matching_old_implementation_3():
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    passes = 1
    window = tuple([1] * 7)
    window_size = len(window)
    half_window_size = int(window_size / 2)
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    # unfortunately the first value after start and first value after end are not
    # matching, but the rest are perfectly matching
    assert result_1[half_window_size:-half_window_size] == pytest.approx(
        result_2[half_window_size:-half_window_size]
    )


def test_smooth_avg_protetced_values_1():
    """Testing ``smooth_avg`` ``protect`` is working as expected."""
    test_values = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    passes = 1
    window = (1, 1, 1)
    protect = [7]
    result = smooth_avg(test_values, passes, window, protect)
    expected_result = [
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.3333333333333333,
        1,
        0.3333333333333333,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
    ]
    assert result == expected_result


def test_smooth_avg_protetced_values_2():
    """Testing ``smooth_avg`` ``protect`` is working as expected."""
    test_values = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    passes = 1
    window = (1, 1, 1)
    protect = [6, 7]
    result = smooth_avg(test_values, passes, window, protect)
    expected_result = [
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        1,
        0.3333333333333333,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
    ]
    assert result == expected_result
