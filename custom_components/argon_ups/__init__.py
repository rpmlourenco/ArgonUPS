"""Argon UPS local serial integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ArgonUPSCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
type ArgonUPSConfigEntry = ConfigEntry[ArgonUPSCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ArgonUPSConfigEntry) -> bool:
    """Connect and forward setup; Home Assistant retries unavailable devices."""
    coordinator = ArgonUPSCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArgonUPSConfigEntry) -> bool:
    """Unload entities and release the serial connection."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unloaded
