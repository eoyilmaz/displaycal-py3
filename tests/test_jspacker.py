import pytest



@pytest.skip(reason="TODO: This test is moved from the module, properly implement it.")
def test_run():
    p = JavaScriptPacker()
    with open(sys.argv[1]) as f:
        script = f.read()
    result = p.pack(script, encoding=62, fastDecode=True, compaction=True)
    with open(f"{sys.argv[1]}pack", "w") as f:
        f.write(result)


@pytest.skip(reason="TODO: This test is moved from the module, properly implement it.")
def test_run1():
    test_scripts = []

    test_scripts.append(
        (
            """// ----------------------------------------------------------------------
// public interface
// -----------------------------------------------------------------------

cssQuery.toString = function() {
    return "function cssQuery() {\n  [version " + version + "]\n}";
};""",
            0,
            False,
            False,
            """cssQuery.toString=function(){return"function cssQuery() {\n  """
            """[version "+version+"]\n}"};""",
        )
    )

    test_scripts.append(
        (
            """function test(_localvar) {
    var $name = 'foo';
    var $$dummy = 2;

    return $name + $$dummy;
}""",
            0,
            False,
            True,
            """function test(_0){var n='foo';var du=2;return n+du}""",
        )
    )

    test_scripts.append(
        (
            """function _test($localvar) {
    var $name = 1;
    var _dummy = 2;
    var __foo = 3;

    return $name + _dummy + $localvar + __foo;
}""",
            0,
            False,
            True,
            """function _1(l){var n=1;var _0=2;var __foo=3;return n+_0+l+__foo}""",
        )
    )

    test_scripts.append(
        (
            """function _test($localvar) {
    var $name = 1;
    var _dummy = 2;
    var __foo = 3;

    return $name + _dummy + $localvar + __foo;
}

function _bar(_ocalvar) {
    var $name = 1;
    var _dummy = 2;
    var __foo = 3;

    return $name + _dummy + $localvar + __foo;
}""",
            0,
            False,
            True,
            """function _3(l){var n=1;var _0=2;var __foo=3;return n+_0+l+__foo}"""
            """function _2(_1){var n=1;var _0=2;var __foo=3;return n+_0+l+__foo}""",
        )
    )

    test_scripts.append(("cssQuery1.js", 0, False, False, "cssQuery1-p1.js"))
    test_scripts.append(("cssQuery.js", 0, False, False, "cssQuery-p1.js"))
    test_scripts.append(("pack.js", 0, False, False, "pack-p1.js"))
    test_scripts.append(("cssQuery.js", 0, False, True, "cssQuery-p2.js"))
    # the following ones are different, because javascript might use an
    # unstable sort algorithm while python uses an stable sort algorithm
    test_scripts.append(("pack.js", 0, False, True, "pack-p2.js"))
    test_scripts.append(
        (
            "test.js",
            0,
            False,
            True,
            """function _4(l){var n=1;var _0=2;var __foo=3;return n+_0+l+__foo}"""
            """function _3(_1){var n=1;var _2=2;var __foo=3;return n+_2+l+__foo}""",
        )
    )
    test_scripts.append(
        (
            "test.js",
            10,
            False,
            False,
            """eval(function(p,a,c,k,e,d){while(c--){if(k[c]){p=p.replace(new RegExp"""
            """("\\b"+e(c)+"\\b","g"),k[c])}}return p}('8 13($6){0 $4=1;0 7=2;0 5=3;"""
            """9 $4+7+$6+5}8 11(12){0 $4=1;0 10=2;0 5=3;9 $4+10+$6+5}',10,14,'var||||"""
            """name|__foo|localvar|_dummy|function|return|_2|_bar|_ocalvar|_test'"""
            """.split('|')))""",
        )
    )
    test_scripts.append(
        (
            "test.js",
            62,
            False,
            False,
            """eval(function(p,a,c,k,e,d){while(c--){if(k[c]){p=p.replace(new RegExp"""
            """("\\b"+e(c)+"\\b","g"),k[c])}}return p}('8 d($6){0 $4=1;0 7=2;0 5=3;9 """
            """$4+7+$6+5}8 b(c){0 $4=1;0 a=2;0 5=3;9 $4+a+$6+5}',14,14,'var||||name|"""
            """__foo|localvar|_dummy|function|return|_2|_bar|_ocalvar|_test'.split('|"""
            """')))""",
        )
    )
    test_scripts.append(("test.js", 95, False, False, "test-p4.js"))
    test_scripts.append(("cssQuery.js", 0, False, True, "cssQuery-p3.js"))
    test_scripts.append(("cssQuery.js", 62, False, True, "cssQuery-p4.js"))

    p = JavaScriptPacker()
    for script, encoding, fastDecode, specialChars, expected in test_scripts:
        if os.path.exists(script):
            with open(script) as f:
                _script = f.read()
        else:
            _script = script
        if os.path.exists(expected):
            with open(expected) as f:
                _expected = f.read()
        else:
            _expected = expected
        print(script[:20], encoding, fastDecode, specialChars, expected[:20])
        print("=" * 40)
        result = p.pack(_script, encoding, fastDecode, specialChars)
        print(len(result), len(_script))
        if result != _expected:
            print("ERROR!!!!!!!!!!!!!!!!")
            print(_expected)
            print(result)
            # print list(difflib.unified_diff(result, _expected))
