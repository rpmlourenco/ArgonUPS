"""Native wake actions with a mocked RTC, never actual host power actions."""

import time
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.argon_ups.client import ArgonUPSError
from custom_components.argon_ups.protocol import UPSStatus

DOMAIN = "argon_ups"


@pytest.fixture
async def wake_setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"port": "/dev/test"})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.argon_ups.coordinator.ArgonUPSClient") as serial,
        patch("custom_components.argon_ups.services.NativeRTC") as rtc_factory,
    ):
        serial.return_value.query.return_value = UPSStatus(20, True)
        serial.return_value.query_diagnostic.side_effect = ArgonUPSError("optional")
        rtc = rtc_factory.return_value
        rtc.schedule.return_value = int(time.time()) + 900
        rtc.cancel.return_value = True
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        binding = {
            "battery_entity": registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_battery"
            ),
            "on_battery_entity": registry.async_get_entity_id(
                "binary_sensor", DOMAIN, f"{entry.entry_id}_on_battery"
            ),
        }
        yield rtc, binding
        await hass.config_entries.async_unload(entry.entry_id)


async def test_schedule_response_and_owned_cancel(hass, wake_setup):
    rtc, binding = wake_setup
    response = await hass.services.async_call(
        DOMAIN,
        "schedule_wake",
        {**binding, "retry_minutes": 15},
        blocking=True,
        return_response=True,
    )
    rtc.schedule.assert_called_once_with(15, None)
    assert response["wake_timestamp"] == rtc.schedule.return_value
    cancelled = await hass.services.async_call(
        DOMAIN, "cancel_wake", binding, blocking=True, return_response=True
    )
    rtc.cancel.assert_called_once_with(response["wake_timestamp"])
    assert cancelled == {"cancelled": True}


@pytest.mark.parametrize(
    "battery,power", [("20", "off"), ("unknown", "on"), ("80", "on")]
)
async def test_restored_power_and_invalid_or_high_battery_do_not_arm(
    hass, wake_setup, battery, power
):
    rtc, binding = wake_setup
    hass.states.async_set(binding["battery_entity"], battery)
    hass.states.async_set(binding["on_battery_entity"], power)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "schedule_wake", {**binding, "retry_minutes": 15}, blocking=True
        )
    rtc.schedule.assert_not_called()


async def test_unregistered_pair_cannot_arm_the_host(hass, wake_setup):
    rtc, binding = wake_setup
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "schedule_wake",
            {**binding, "battery_entity": "sensor.unregistered", "retry_minutes": 15},
            blocking=True,
        )
    rtc.schedule.assert_not_called()
