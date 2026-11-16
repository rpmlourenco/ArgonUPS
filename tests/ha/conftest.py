"""Run these tests with the real Home Assistant test framework on Linux."""

import pytest


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    """Allow loading the integration under test."""
