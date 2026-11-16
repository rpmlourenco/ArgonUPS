"""Battery percentage sensor."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE

from .entity import ArgonUPSEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add the battery sensor."""
    async_add_entities([ArgonUPSBattery(entry.runtime_data, entry.entry_id, "battery")])


class ArgonUPSBattery(ArgonUPSEntity, SensorEntity):
    """UPS-reported battery percentage."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> int:
        return self.coordinator.data.battery_percent
