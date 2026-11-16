"""Run these tests with the real Home Assistant test framework on Linux."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    """Allow loading the integration under test."""


@pytest.fixture(autouse=True)
def no_host_usb_scan():
    """Mock only USB dependency setup; discovery events are supplied by tests."""
    with patch("homeassistant.components.usb.async_setup", return_value=True):
        yield
