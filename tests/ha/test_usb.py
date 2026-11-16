"""USB discovery and duplicate prevention with the Home Assistant framework."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.components import usb
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.loader import async_get_usb
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "argon_ups"
PERSISTENT_PORT = "/dev/serial/by-id/usb-Argon_Argon_USB_TEST-if00"


async def test_home_assistant_registers_custom_usb_matcher(hass):
    matchers = await async_get_usb(hass)
    argon = [matcher for matcher in matchers if matcher["domain"] == DOMAIN]
    assert len(argon) == 1
    assert usb.usb_device_matches_matcher(discovery(), argon[0])


def discovery(**changes):
    """Build reported USB metadata without claiming a physical device test."""
    values = {
        "device": "/dev/ttyACM0",
        "vid": "1D6B",
        "pid": "0104",
        "serial_number": "TEST",
        "manufacturer": "Argon",
        "description": "Argon_USB",
    }
    return UsbServiceInfo(**(values | changes))


async def test_usb_discovery_prefills_port_without_serial_query(hass):
    with (
        patch(
            "custom_components.argon_ups.config_flow.usb.get_serial_by_id",
            return_value=PERSISTENT_PORT,
        ),
        patch("custom_components.argon_ups.config_flow.probe") as probe,
        patch("custom_components.argon_ups.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USB}, data=discovery()
        )
        assert result["type"] == "form"
        assert result["data_schema"]({}) == {"port": PERSISTENT_PORT}
        probe.assert_not_called()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": PERSISTENT_PORT}
        )
        assert result["type"] == "create_entry"
        assert result["data"] == {"port": PERSISTENT_PORT}
        assert result["result"].unique_id == PERSISTENT_PORT
        probe.assert_called_once_with(PERSISTENT_PORT)
        await hass.async_block_till_done()


@pytest.mark.parametrize("source", [SOURCE_USB, SOURCE_USER])
async def test_discovery_and_manual_alias_do_not_duplicate(hass, source):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=PERSISTENT_PORT, data={"port": PERSISTENT_PORT}
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.argon_ups.config_flow.usb.get_serial_by_id",
            return_value=PERSISTENT_PORT,
        ),
        patch("custom_components.argon_ups.config_flow.probe") as probe,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=discovery() if source == SOURCE_USB else {"port": "/dev/ttyACM0"},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"
        probe.assert_not_called()


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, True),
        ({"manufacturer": "ARGON", "description": "Argon_USB - interface 0"}, True),
        ({"manufacturer": "Linux", "description": "USB Gadget"}, False),
        ({"manufacturer": None}, False),
        ({"description": None}, False),
        ({"vid": "FFFF"}, False),
        ({"pid": "FFFF"}, False),
    ],
)
def test_manifest_does_not_claim_unrelated_usb_devices(changes, expected):
    manifest = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "custom_components/argon_ups/manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        usb.usb_device_matches_matcher(discovery(**changes), manifest["usb"][0])
        is expected
    )
