"""Evaluate the actual blueprint guard offline, never calling a service."""

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jinja2.nativetypes import NativeEnvironment


class InputLoader(yaml.SafeLoader):
    """Retain blueprint inputs as names for structural assertions."""


InputLoader.add_constructor(
    "!input", lambda loader, node: loader.construct_scalar(node)
)
BLUEPRINT = yaml.load(
    (
        Path(__file__).resolve().parents[2]
        / "blueprints/automation/argon_ups_safe_shutdown.yaml"
    ).read_text(encoding="utf-8"),
    Loader=InputLoader,
)
GUARD = BLUEPRINT["triggers"][0]["value_template"]
NOW = datetime(2026, 11, 16, 22, tzinfo=UTC)
BATTERY = "sensor.test_battery"
POWER = "binary_sensor.test_on_battery"


class States(dict):
    def __call__(self, entity_id):
        return self[entity_id].state if entity_id in self else "unknown"


def samples(battery="30", power="on"):
    return States(
        {
            BATTERY: SimpleNamespace(state=battery, last_reported=NOW),
            POWER: SimpleNamespace(state=power, last_reported=NOW),
        }
    )


def evaluate(states, enabled=True, devices=None):
    def is_number(value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    environment = NativeEnvironment()
    environment.globals.update(
        states=states,
        now=lambda: NOW,
        as_timestamp=lambda value, default=0: (
            value.timestamp() if isinstance(value, datetime) else default
        ),
        is_number=is_number,
        is_state=lambda entity_id, state: states(entity_id) == state,
        device_id=lambda entity_id: (devices or {BATTERY: "ups-1", POWER: "ups-1"}).get(
            entity_id
        ),
    )
    result = environment.from_string(GUARD).render(
        battery_entity=BATTERY,
        on_battery_entity=POWER,
        shutdown_threshold=30,
        max_age_seconds=30,
        shutdown_enabled=enabled,
    )
    return result is True or (isinstance(result, str) and result.strip() == "True")


@pytest.mark.parametrize(
    ("battery", "expected"),
    [
        ("0", True),
        ("20", True),
        ("30", True),
        ("30.1", False),
        ("100", False),
        ("-1", False),
        ("101", False),
        ("unknown", False),
        ("unavailable", False),
        ("", False),
        ("nan", False),
        ("inf", False),
        ("-inf", False),
    ],
)
def test_battery_values(battery, expected):
    assert evaluate(samples(battery=battery)) is expected


@pytest.mark.parametrize("power", ["off", "unknown", "unavailable", "", "garbage"])
def test_external_power_and_invalid_state_block_shutdown(power):
    assert not evaluate(samples(power=power))


@pytest.mark.parametrize("entity_id", [BATTERY, POWER])
@pytest.mark.parametrize("age", [-1, 0, 30, 31, 600])
def test_timestamp_bounds(entity_id, age):
    states = samples()
    states[entity_id].last_reported = NOW - timedelta(seconds=age)
    assert evaluate(states) is (0 <= age <= 30)


@pytest.mark.parametrize("entity_id", [BATTERY, POWER])
def test_missing_entity(entity_id):
    states = samples()
    del states[entity_id]
    assert not evaluate(states)


@pytest.mark.parametrize("enabled", [False, None, "false", "true", 1, "on"])
def test_only_explicit_boolean_true_arms_shutdown(enabled):
    assert not evaluate(samples(), enabled=enabled)


@pytest.mark.parametrize(
    "devices", [{BATTERY: "ups-1", POWER: "ups-2"}, {BATTERY: None, POWER: None}]
)
def test_sensors_must_belong_to_same_registered_device(devices):
    assert not evaluate(samples(), devices=devices)


def test_explicit_arming_and_action_recheck():
    assert not evaluate(samples(), enabled=False)
    assert BLUEPRINT["blueprint"]["input"]["shutdown_enabled"]["default"] is False
    assert BLUEPRINT["blueprint"]["input"]["shutdown_threshold"]["default"] == 30
    assert BLUEPRINT["blueprint"]["input"]["confirmation_seconds"]["default"] == 30
    assert BLUEPRINT["blueprint"]["input"]["max_age_seconds"]["default"] == 30
    assert BLUEPRINT["actions"][0] == {
        "condition": "trigger",
        "id": "confirmed_low_battery",
    }
    assert BLUEPRINT["actions"][1]["value_template"] == GUARD
    assert BLUEPRINT["actions"][2] == {"action": "hassio.host_shutdown", "data": {}}
    assert BLUEPRINT["triggers"][0]["for"] == {"seconds": "confirmation_seconds"}
    # A final recheck must block both restored mains and stale telemetry.
    states = samples()
    assert evaluate(states)
    states[POWER].state = "off"
    assert not evaluate(states)
    states[POWER].state = "on"
    states[BATTERY].last_reported = NOW - timedelta(seconds=31)
    assert not evaluate(states)
