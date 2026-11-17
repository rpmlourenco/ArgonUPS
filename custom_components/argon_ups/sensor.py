"""Battery percentage sensor."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory

from .entity import ArgonUPSEntity
from .protocol import ReadCommand


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add the battery sensor."""
    async_add_entities(
        [
            ArgonUPSBattery(entry.runtime_data, entry.entry_id, "battery"),
            *(
                ArgonUPSDiagnostic(entry.runtime_data, entry.entry_id, command, key)
                for command, key in (
                    (ReadCommand.CHARGE_CURRENT, "charge_current_raw"),
                    (ReadCommand.VERSION, "ups_version"),
                    (ReadCommand.RTC, "rtc"),
                    (ReadCommand.NEXT_START, "next_start"),
                )
            ),
        ]
    )


class ArgonUPSBattery(ArgonUPSEntity, SensorEntity):
    """UPS-reported battery percentage."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> int:
        return self.coordinator.data.battery_percent


class ArgonUPSDiagnostic(ArgonUPSEntity, SensorEntity):
    """An independently available optional readout."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry_id: str, command: ReadCommand, key: str):
        super().__init__(coordinator, entry_id, key)
        self.command = command
        self._attr_translation_key = key
        if command in (ReadCommand.RTC, ReadCommand.NEXT_START):
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.readings[self.command] is not None

    @property
    def native_value(self):
        reading = self.coordinator.readings[self.command]
        return reading.value if reading is not None else None

    @property
    def extra_state_attributes(self):
        reading = self.coordinator.readings[self.command]
        if reading is None:
            return None
        attributes = {"raw_payload": reading.payload.hex(" ")}
        if self.command in (ReadCommand.RTC, ReadCommand.NEXT_START):
            attributes["time_interpretation"] = "UTC following official reader"
            if reading.value is None:
                attributes["interpretation"] = "unset_or_undocumented_alarm_encoding"
        elif self.command == ReadCommand.CHARGE_CURRENT:
            attributes["interpretation"] = (
                "unsigned 16-bit big-endian; unit and scale unverified"
            )
        return attributes
