# -*- coding: utf-8 -*-

from DisplayCAL.util_str import (
    asciize,
    ellipsis_,
    make_ascii_printable,
    make_filename_safe,
    safe_basestring,
    safe_str,
    strtr,
)
from DisplayCAL.icc_profile import TextDescriptionType


def test_asciize_working_properly_1():
    """testing if the ``asciize`` function is working properly str input"""
    tag_data = b"\0" * 8 + b"\x00\x00\x00\x04" + b"test" + b"\0" * 12
    description_type = TextDescriptionType(tagData=tag_data, tagSignature="desc")
    description = str(description_type)
    result = asciize(description)
    expected_result = b"test"
    assert result == expected_result


def test_asciize_working_properly_2():
    """testing if the ``asciize`` function is working properly Exception input"""
    tag_data = b"\0" * 8 + b"\x00\x00\x00\x04" + b"te\x80t" + b"\0" * 12
    description_type = TextDescriptionType(tagData=tag_data, tagSignature="desc")
    result = str(description_type)
    expected_result = "te�t"  # TODO: I'm not sure if this is the expected result
    assert result == expected_result


def test_safe_basestring_1():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError("test the Environment is not being correct")
    assert safe_basestring(env_error) == "test the Environment is not being correct"


def test_safe_basestring_2():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError()
    env_error.reason = "test the Environment is not being correct"
    assert safe_basestring(env_error) == "test the Environment is not being correct"


def test_safe_basestring_3():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError()
    env_error.reason = b"test the Environment is not being correct"
    assert safe_basestring(env_error) == "test the Environment is not being correct"


def test_safe_basestring_4():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError()
    env_error.reason = ["test the Environment is not being correct"]
    assert safe_basestring(env_error) == "test the Environment is not being correct"


def test_safe_basestring_5():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError()
    env_error.reason = [b"test the Environment is not being correct"]
    assert safe_basestring(env_error) == "test the Environment is not being correct"


def test_safe_basestring_6():
    """testing if safe_basestring() is working properly"""
    env_error = EnvironmentError()
    env_error.reason = [123]
    assert safe_basestring(env_error) == "123"


def test_safe_basestring_7():
    """testing if safe_basestring() is working properly"""

    class TestObj:
        def __init__(self):
            self.filename = "TestValue.ti3"

    env_error = EnvironmentError()
    test_obj = TestObj()
    env_error.reason = [test_obj]
    assert safe_basestring(env_error) == test_obj.__repr__()


def test_safe_basestring_8():
    """testing if safe_basestring() is working properly"""
    key_error = KeyError("test some key values not being correct")
    assert (
        safe_basestring(key_error)
        == "Key does not exist: 'test some key values not being correct'"
    )


def test_safe_basestring_9():
    """testing if safe_basestring() is working properly"""
    from _socket import gaierror

    gai_error = gaierror("test some key values not being correct")
    assert safe_basestring(gai_error) == "test some key values not being correct"


def test_safe_basestring_10():
    """testing if safe_basestring() is working properly"""
    gai_error = OSError("test some key values not being correct")
    assert safe_basestring(gai_error) == "test some key values not being correct"


def test_safe_string_1():
    """testing if safe_string() is working properly"""
    obj = "Test value"
    assert safe_str(obj) == "Test value"


def test_safe_string_2():
    """testing if safe_string() is working properly"""
    obj = b"Test value"
    assert safe_str(obj) == "Test value"


def test_strtr_1():
    """testing if the strtr() is working properly"""
    test_value = b"test1, test2, test3"
    replacements = [[b"test1", b"value1"], [b"test2", b"value2"], [b"test3", b"value3"]]
    result = strtr(test_value, replacements)
    expected_result = b"value1, value2, value3"
    assert result == expected_result


def test_strtr_2():
    """testing if the strtr() is working properly"""
    test_value = "test1, test2, test3"
    replacements = [["test1", "value1"], ["test2", "value2"], ["test3", "value3"]]
    result = strtr(test_value, replacements)
    expected_result = "value1, value2, value3"
    assert result == expected_result


def test_strtr_3():
    """testing if the strtr() is working properly"""
    test_value = b"test1, test2, test3"
    replacements = {b"test1": b"value1", b"test2": b"value2", b"test3": b"value3"}
    result = strtr(test_value, replacements)
    expected_result = b"value1, value2, value3"
    assert result == expected_result


def test_strtr_4():
    """testing if the strtr() is working properly"""
    test_value = "test1, test2, test3"
    replacements = {"test1": "value1", "test2": "value2", "test3": "value3"}
    result = strtr(test_value, replacements)
    expected_result = "value1, value2, value3"
    assert result == expected_result


def test_ellipsis_1():
    """testing ellipsis with str input"""
    test_value = "some long str"
    expected_result = "some long\u2026"
    result = ellipsis_(test_value, 10)
    assert result == expected_result


def test_ellipsis_2():
    """testing ellipsis with bytes input"""
    test_value = b"some long bytes sequence"
    expected_result = b"some longu\xc2\x826"
    result = ellipsis_(test_value, 10)
    assert result == expected_result


def test_make_filename_safe_1():
    """testing make_filename_safe with str input"""
    test_value = "some proper values that is suitable for filesystem already"
    result = make_filename_safe(test_value)
    expected_result = "some proper values that is suitable for filesystem already"
    assert result == expected_result


def test_make_filename_safe_2():
    """testing make_filename_safe with str input"""
    test_value = "this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value)
    expected_result = "this_is not_suitable_for_filesystem _"
    assert result == expected_result


def test_make_filename_safe_3():
    """testing make_filename_safe with str input and substitute (str)"""
    test_value = "this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value, substitute="-")
    expected_result = "this-is not-suitable-for-filesystem -"
    assert result == expected_result


def test_make_filename_safe_4():
    """testing make_filename_safe with str input and substitute (bytes)"""
    test_value = "this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value, substitute=b"-")
    expected_result = "this-is not-suitable-for-filesystem -"
    assert result == expected_result


def test_make_filename_safe_5():
    """testing make_filename_safe with str input"""
    test_value = b"some proper values that is suitable for filesystem already"
    result = make_filename_safe(test_value)
    expected_result = b"some proper values that is suitable for filesystem already"
    assert result == expected_result


def test_make_filename_safe_6():
    """testing make_filename_safe with str input"""
    test_value = b"this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value)
    expected_result = b"this_is not_suitable_for_filesystem _"
    assert result == expected_result


def test_make_filename_safe_7():
    """testing make_filename_safe with str input and substitute (str)"""
    test_value = b"this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value, substitute="-")
    expected_result = b"this-is not-suitable-for-filesystem -"
    assert result == expected_result


def test_make_filename_safe_8():
    """testing make_filename_safe with str input and substitute (bytes)"""
    test_value = b"this/is not:suitable*for?filesystem \\"
    result = make_filename_safe(test_value, substitute=b"-")
    expected_result = b"this-is not-suitable-for-filesystem -"
    assert result == expected_result


def test_make_ascii_printable_1():
    """Test DisplayCAL.util_str.make_ascii_printable() function."""
    test_value = b"TYPR371U504L\n"
    result = make_ascii_printable(test_value, substitute=b"\x00")
    expected_result = b"TYPR371U504L\n"
    assert result == expected_result


def test_make_ascii_printable_2():
    """Test DisplayCAL.util_str.make_ascii_printable() function."""
    test_value = b"\xcf\xff\xaf\xf0\x99\x80TYPR371U504L\n"
    result = make_ascii_printable(test_value, substitute=b"\x00")
    expected_result = b"\x00\x00\x00\x00\x00\x00TYPR371U504L\n"
    assert result == expected_result


def test_make_ascii_printable_3():
    """Test DisplayCAL.util_str.make_ascii_printable() function."""
    test_value = b"\xcf\xff\xaf\xf0\x99\x80TYPR371U504L\n"
    result = make_ascii_printable(test_value, substitute="\x00")
    expected_result = b"\x00\x00\x00\x00\x00\x00TYPR371U504L\n"
    assert result == expected_result


def test_make_ascii_printable_4():
    """Test DisplayCAL.util_str.make_ascii_printable() function."""
    test_value = "\xcf\xff\xaf\xf0\x99\x80TYPR371U504L\n"
    result = make_ascii_printable(test_value, substitute=b"\x00")
    expected_result = "\x00\x00\x00\x00\x00\x00TYPR371U504L\n"
    assert result == expected_result
