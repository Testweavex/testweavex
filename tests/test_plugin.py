import pytest


def test_plugin_captures_passing_test(pytester):
    pytester.makepyfile("""
        def test_always_passes():
            assert True
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(passed=1)


def test_plugin_captures_failing_test(pytester):
    pytester.makepyfile("""
        def test_always_fails():
            assert False
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(failed=1)


def test_plugin_captures_skipped_test(pytester):
    pytester.makepyfile("""
        import pytest
        @pytest.mark.skip(reason="not ready")
        def test_skipped():
            pass
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(skipped=1)


def test_plugin_accepts_testweavex_flags(pytester):
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest(
        "--suite=my-suite",
        "--environment=staging",
        "--tb=short",
    )
    result.assert_outcomes(passed=1)


def test_plugin_creates_db_file(pytester):
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    pytester.runpytest("--tb=short")
    db_path = pytester.path / ".testweavex" / "results.db"
    assert db_path.exists()


def test_plugin_tw_type_marker(pytester):
    pytester.makepyfile("""
        import pytest
        @pytest.mark.tw_type("e2e")
        def test_e2e_style():
            assert True
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(passed=1)
