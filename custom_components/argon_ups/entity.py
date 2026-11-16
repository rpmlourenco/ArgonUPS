"""Common device information for Argon UPS entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import ArgonUPSCoordinator


class ArgonUPSEntity(CoordinatorEntity[ArgonUPSCoordinator]):
    """An entity backed by a single shared UPS coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArgonUPSCoordinator, entry_id: str, key: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=NAME,
            manufacturer="Argon40",
            model="Argon PWR UPS 27W 5000mAh",
        )
