"""Configuration, entities, availability, retry and unload with real HA."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.argon_ups.client import ArgonUPSError
from custom_components.argon_ups.protocol import UPSStatus

DOMAIN = "argon_ups"


async def test_config_flow(hass):
    with patch("custom_components.argon_ups.config_flow.probe") as probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == "form"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": " /dev/test "}
        )
        assert result["type"] == "create_entry"
        assert result["data"] == {"port": "/dev/test"}
        probe.assert_called_once_with("/dev/test")
        await hass.async_block_till_done()


async def test_flow_failure_and_invalid_port(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"port": "socket://host"}
    )
    assert result["errors"] == {"port": "invalid_port"}
    with patch(
        "custom_components.argon_ups.config_flow.probe",
        side_effect=ArgonUPSError("offline"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"port": "/dev/test"}
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="/dev/test", data={"port": "/dev/test"}
    )
    entry.add_to_hass(hass)
    with patch("custom_components.argon_ups.config_flow.probe") as probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"port": "/dev/test"}
        )
    assert result["reason"] == "already_configured"
    probe.assert_not_called()


async def test_entities_recovery_and_unload(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Argon UPS",
        data={"port": "/dev/test"},
        unique_id="/dev/test",
    )
    entry.add_to_hass(hass)
    with patch("custom_components.argon_ups.coordinator.ArgonUPSClient") as factory:
        client = factory.return_value
        client.query.return_value = UPSStatus(75, False)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        states = hass.states.async_all()
        battery = next(s for s in states if s.entity_id.startswith("sensor.argon_ups"))
        power = next(
            s for s in states if s.entity_id.startswith("binary_sensor.argon_ups")
        )
        assert battery.state == "75"
        assert battery.attributes["unit_of_measurement"] == "%"
        assert power.state == "off"
        client.query.side_effect = ArgonUPSError("unplugged")
        await entry.runtime_data.async_refresh()
        assert hass.states.get(battery.entity_id).state == STATE_UNAVAILABLE
        assert hass.states.get(power.entity_id).state == STATE_UNAVAILABLE
        client.query.side_effect = None
        client.query.return_value = UPSStatus(70, True)
        await entry.runtime_data.async_refresh()
        assert hass.states.get(battery.entity_id).state == "70"
        assert hass.states.get(power.entity_id).state == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)
        client.close.assert_called()


async def test_initial_failure_retries_and_closes(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"port": "/dev/test"})
    entry.add_to_hass(hass)
    with patch("custom_components.argon_ups.coordinator.ArgonUPSClient") as factory:
        factory.return_value.query.side_effect = ArgonUPSError("offline")
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        factory.return_value.close.assert_called()
