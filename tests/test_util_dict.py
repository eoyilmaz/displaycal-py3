from DisplayCAL.util_dict import dict_slice, dict_sort


def test_dict_slice_1():
    """Test dict_slice with dict."""
    a = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    assert dict_slice(a, 2, 5) == {
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
    }


def test_dict_slice_2():
    """Test dict_slice with dict."""
    initial_dict = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    a = dict(initial_dict)
    assert a == initial_dict
    assert dict_slice(a, 2, 5) == {
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
    }


def test_dict_slice_3():
    """Test dict_slice with dict."""
    a = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    assert dict_slice(a, 2) == {
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }


def test_dict_slice_4():
    """Test dict_slice with dict."""
    a = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    assert dict_slice(a, None, 2) == {1: "b", 3: "a"}


def test_dict_slice_5():
    """Test dict_slice with dict."""
    a = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    assert dict_slice(a) == a


def test_dict_sort_1():
    """Test dict_sort with dict."""
    a = {
        3: "a",  # 0
        1: "b",  # 1
        2: "c",  # 2
        10: "d",  # 3
        5: "e",  # 4
        123: "f",  # 5
        55: "g",  # 6
    }
    assert dict_sort(a) == {
        1: "b",
        2: "c",
        3: "a",
        5: "e",
        10: "d",
        55: "g",
        123: "f",
    }


def test_dict_sort_2():
    """Test dict_sort with dict."""
    a = {
        "3": "a",  # 0
        "1": "b",  # 1
        "2": "c",  # 2
        "10": "d",  # 3
        "5": "e",  # 4
        "123": "f",  # 5
        "55": "g",  # 6
    }
    assert dict_sort(a, key=lambda s: int(s)) == {
        "1": "b",
        "2": "c",
        "3": "a",
        "5": "e",
        "10": "d",
        "55": "g",
        "123": "f",
    }


def test_dict_sort_3():
    """Test dict_sort with dict."""
    a = {
        "3": "a",  # 0
        "1": "b",  # 1
        "2": "c",  # 2
        "10": "d",  # 3
        "5": "e",  # 4
        "123": "f",  # 5
        "55": "g",  # 6
    }
    assert dict_sort(a, key=lambda s: s.lower()) == {
        "1": "b",
        "2": "c",
        "3": "a",
        "5": "e",
        "10": "d",
        "55": "g",
        "123": "f",
    }
