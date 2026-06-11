pytest_plugins = ["pytester"]

import pytest


@pytest.fixture
def pytester(pytester):
    # Prevent pytest-playwright (and other optional local plugins) from loading
    # inside pytester subprocess runs — their hook wrappers conflict with the
    # testweavex plugin and cause false failures when those packages are installed.
    pytester.makeini("[pytest]\naddopts = -p no:playwright -p no:base-url\n")
    return pytester
