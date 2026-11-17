"""Explicit native RTC actions; neither action shuts down or restarts the host."""

import asyncio
import logging
import math
from datetime import UTC, datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .rtc import NativeRTC, RTCError

_LOGGER = logging.getLogger(__name__)
_BINDING_SCHEMA = {
    vol.Required("battery_entity"): cv.entity_id,
    vol.Required("on_battery_entity"): cv.entity_id,
}
SCHEDULE_SCHEMA = vol.Schema(
    {
        **_BINDING_SCHEMA,
        vol.Required("retry_minutes"): vol.All(
            cv.positive_int, vol.Range(min=5, max=1440)
        ),
        vol.Optional("max_age_seconds", default=30): vol.All(
            cv.positive_int, vol.Range(min=15, max=60)
        ),
        vol.Optional("shutdown_threshold", default=30): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=50)
        ),
    }
)


def _validate_binding(hass: HomeAssistant, data: dict) -> None:
    """Require the selected battery/power pair from one loaded Argon entry."""
    registry = er.async_get(hass)
    battery = registry.async_get(data["battery_entity"])
    power = registry.async_get(data["on_battery_entity"])
    if (
        battery is None
        or power is None
        or battery.platform != DOMAIN
        or power.platform != DOMAIN
        or battery.config_entry_id is None
        or battery.config_entry_id != power.config_entry_id
        or battery.device_id is None
        or battery.device_id != power.device_id
        or battery.unique_id != f"{battery.config_entry_id}_battery"
        or power.unique_id != f"{battery.config_entry_id}_on_battery"
    ):
        raise HomeAssistantError(
            "Select battery and on-battery entities from one Argon UPS"
        )
    entry = hass.config_entries.async_get_entry(battery.config_entry_id)
    if entry is None or entry.state != ConfigEntryState.LOADED:
        raise HomeAssistantError("The selected Argon UPS integration is not loaded")


def _validate_low_battery(hass: HomeAssistant, data: dict) -> None:
    """Do not arm recovery from missing, old or external-power telemetry."""
    now = datetime.now(UTC)
    for key in ("battery_entity", "on_battery_entity"):
        state = hass.states.get(data[key])
        if (
            state is None
            or not 0
            <= (now - state.last_reported).total_seconds()
            <= data["max_age_seconds"]
        ):
            raise HomeAssistantError(
                "Fresh UPS telemetry is required to schedule a wake"
            )
    battery = hass.states.get(data["battery_entity"])
    power = hass.states.get(data["on_battery_entity"])
    try:
        level = float(battery.state)
    except (TypeError, ValueError) as err:
        raise HomeAssistantError("Invalid UPS battery percentage") from err
    if (
        not math.isfinite(level)
        or not 0 <= level <= data["shutdown_threshold"]
        or power.state != "on"
    ):
        raise HomeAssistantError("A confirmed low battery on battery power is required")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register alarm actions once, remembering only the alarm we own."""
    rtc = NativeRTC()
    store = Store(hass, 1, f"{DOMAIN}.native_wake")
    try:
        saved = await store.async_load()
    except (HomeAssistantError, OSError, ValueError) as err:
        # Optional recovery metadata must not prevent battery/power monitoring.
        # Unknown ownership also means an existing alarm cannot be replaced.
        _LOGGER.warning("Cannot restore native wake alarm ownership: %s", err)
        saved = None
    owned_alarm = saved.get("alarm") if isinstance(saved, dict) else None
    if type(owned_alarm) is not int:
        owned_alarm = None
    lock = asyncio.Lock()

    async def schedule(call: ServiceCall) -> dict:
        nonlocal owned_alarm
        async with lock:
            _validate_binding(hass, call.data)
            _validate_low_battery(hass, call.data)
            try:
                deadline = await hass.async_add_executor_job(
                    rtc.schedule, call.data["retry_minutes"], owned_alarm
                )
                owned_alarm = deadline
                # Persist before returning: the host may shut down immediately.
                await store.async_save({"alarm": deadline})
            except RTCError as err:
                raise HomeAssistantError(str(err)) from err
            _LOGGER.info(
                "Native Pi RTC wake scheduled for %s",
                datetime.fromtimestamp(deadline, UTC),
            )
            return {
                "wake_timestamp": deadline,
                "wake_time": datetime.fromtimestamp(deadline, UTC).isoformat(),
            }

    async def cancel(call: ServiceCall) -> dict:
        nonlocal owned_alarm
        async with lock:
            _validate_binding(hass, call.data)
            try:
                cancelled = await hass.async_add_executor_job(rtc.cancel, owned_alarm)
            except RTCError as err:
                raise HomeAssistantError(str(err)) from err
            owned_alarm = None
            await store.async_save({"alarm": None})
            return {"cancelled": cancelled}

    hass.services.async_register(
        DOMAIN,
        "schedule_wake",
        schedule,
        schema=SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "cancel_wake",
        cancel,
        schema=vol.Schema(_BINDING_SCHEMA),
        supports_response=SupportsResponse.OPTIONAL,
    )
