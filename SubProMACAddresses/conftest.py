"""
conftest.py — shared pytest options for SubProMACAddresses test suite.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--cycles",
        type=int,
        default=5,
        help="Number of provisioning cycles per ARP delay in stress test (default: 5)",
    )
    parser.addoption(
        "--mac-count",
        type=int,
        default=10,
        help=(
            "Number of MACs to provision in the exhaustion test. "
            "The pool is filled to exactly this count, then one more attempt "
            "verifies the pool-exhausted error path (default: 10)."
        ),
    )


@pytest.fixture(scope="session")
def cycles(request):
    return request.config.getoption("--cycles")


@pytest.fixture(scope="session")
def mac_count(request):
    return request.config.getoption("--mac-count")
