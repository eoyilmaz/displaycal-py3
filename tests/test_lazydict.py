
# PyYAML
from io import StringIO
import yaml

import pytest

from DisplayCAL.lazydict import LazyDict_YAML_Lite


@pytest.mark.parametrize(
    "doc, do_assert", [
        ['TEST: \n  "ABC\n\n  DEF\n"  \n    \n\n\n\n', True],
        ['TEST: \n  "ABC\n\n  DEF"', True],
        ['TEST: \n  "ABC\n  DEF\n"', True],
        ['TEST: \n  "ABC\n\n  DEF\tG\n  \n    \n\n\n\n \t"', True],
        ["TEST: \n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        ['TEST: \n  "ABC\n\n  DEF\n"', True],
        ["TEST: \n  ABC\n\n DEFG\n  \n    \n\n\n\n ", True],
        ['TEST: \n  "ABC\n\n DEF\tG\n  \n    \n\n\n\n" ', True],
        ["TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        ["TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        ["TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        # ["TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        # ["TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        # ["TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n", True],
        ['TEST: "\n ABC\n\n  DEFG\n  \n    \n\n\n\n"', True],
        ["TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        ["TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        ["TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        # ['TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ', True],
        # ['TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ', True],
        # ['TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ', True],
        ['TEST : |\n  "\n  ABC\n\n  DEFG\n  \n    \n\n\n\n  "', True],
        ["TEST: |-\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        ["TEST: |\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        ["TEST:\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ", True],
        ["TEST: |- # Comment\n  Value", True],
        ["TEST: |- # Comment\n  Value # Not A Comment\n  # Not A Comment", True],
        ["TEST: # Comment", False],
    ]
)
def test_yaml_lite_to_yaml_conformance(doc, do_assert):
    """Testing YAML Lite to YAML conformance."""
    # print("-" * 80)
    # print(repr(doc))
    a = LazyDict_YAML_Lite(debug=True)
    a.parse(StringIO(doc))
    # print("LazyDict_YAML_Lite", a)
    b = yaml.safe_load(StringIO(doc))
    # print("yaml.YAML         ", b)
    if do_assert:
        assert isinstance(a, dict) and isinstance(b, dict) and a == b


# def test_lazzy_dict():

#     print("=" * 80)
#     print("Performance test")

#     io = StringIO(
#         """{"test1": "Value 1",
# "test2": "Value 2 Line 1\\nValue 2 Line 2\\n\\nValue 2 Line 4\\n",
# "test3": "Value 3 Line 1\\n",
# "test4": "Value 4"}
# """
#     )

#     d = JSONDict()
#     ts = time()
#     for i in range(10000):
#         d.parse(io)
#         io.seek(0)
#     jt = time() - ts

#     d = LazyDict_JSON()
#     ts = time()
#     for i in range(10000):
#         d.parse(io)
#         io.seek(0)
#     ljt = time() - ts

#     io = StringIO(
#         """"test1": Value 1
# "test2": |-
#   Value 2 Line 1
#   Value 2 Line 2

#   Value 2 Line 4
# "test3": |-
#   Value 3 Line 1
# "test4": "Value 4"
# """
#     )

#     d = LazyDict_YAML_UltraLite()
#     ts = time()
#     for i in range(10000):
#         d.parse(io)
#         io.seek(0)
#     yult = time() - ts

#     d = LazyDict_YAML_Lite()
#     ts = time()
#     for i in range(10000):
#         d.parse(io)
#         io.seek(0)
#     ylt = time() - ts

#     ts = time()
#     for i in range(10000):
#         yaml.safe_load(io)
#         io.seek(0)
#     yt = time() - ts

#     ts = time()
#     for i in range(10000):
#         yaml.load(io, Loader=CSafeLoader)
#         io.seek(0)
#     yct = time() - ts

#     print("JSONDict(demjson): %.3fs" % jt)
#     print("LazyDict_JSON: %.3fs" % ljt)
#     print(
#         "LazyDict_YAML_UltraLite: %.3fs," % yult,
#         "vs JSONDict: %.1fx speed," % round(jt / yult, 1),
#         "vs YAML_Lite: %.1fx speed," % round(ylt / yult, 1),
#         "vs PyYAML: %.1fx speed," % round(yt / yult, 1),
#     )
#     print(
#         "LazyDict_YAML_Lite: %.3fs," % ylt,
#         "vs JSONDict: %.1fx speed," % round(jt / ylt, 1),
#         "vs PyYAML: %.1fx speed," % round(yt / ylt, 1),
#     )
#     print("yaml.safe_load: %.3fs" % yt)
#     print("yaml.load(CSafeLoader): %.3fs" % yct)