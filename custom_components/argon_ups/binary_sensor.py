"""UPS power-source sensor."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ArgonUPSEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add the on-battery sensor."""
    async_add_entities(
        [ArgonUPSOnBattery(entry.runtime_data, entry.entry_id, "on_battery")]
    )


class ArgonUPSOnBattery(ArgonUPSEntity, BinarySensorEntity):
    """On means battery power; off means external power."""

    _attr_translation_key = "on_battery"
    _attr_icon = "mdi:battery-arrow-down"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.on_battery
