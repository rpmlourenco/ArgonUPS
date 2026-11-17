"""Validate the blueprint through HA's own schemas without executing actions."""

from pathlib import Path

from homeassistant.components.automation.config import (
    AUTOMATION_BLUEPRINT_SCHEMA,
    async_validate_config_item,
)
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.util.yaml import load_yaml

BLUEPRINT_PATH = (
    Path(__file__).resolve().parents[2]
    / "blueprints/automation/argon_ups_safe_shutdown.yaml"
)


async def test_blueprint_expands_to_valid_home_assistant_automation(hass):
    path = BLUEPRINT_PATH
    data = await hass.async_add_executor_job(load_yaml, str(path))
    blueprint = Blueprint(
        data, expected_domain="automation", schema=AUTOMATION_BLUEPRINT_SCHEMA
    )
    assert blueprint.validate() is None
    inputs = BlueprintInputs(
        blueprint,
        {
            "alias": "Test Argon shutdown - never executed",
            "use_blueprint": {
                "path": str(path),
                "input": {
                    "battery_entity": "sensor.test_battery",
                    "on_battery_entity": "binary_sensor.test_on_battery",
                },
            },
        },
    )
    expanded = inputs.async_substitute()
    assert expanded["variables"]["shutdown_enabled"] is False
    assert expanded["variables"]["retry_enabled"] is False
    assert expanded["actions"][3]["then"][0]["data"]["retry_minutes"] == 15
    assert expanded["triggers"][0]["for"] == {"seconds": 30}
    validated = await async_validate_config_item(hass, "automation", expanded)
    assert validated is not None
