"""Coordinate status polling and entity availability."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ArgonUPSClient, ArgonUPSError
from .const import NAME, POLL_INTERVAL_SECONDS
from .protocol import UPSStatus

_LOGGER = logging.getLogger(__name__)


class ArgonUPSCoordinator(DataUpdateCoordinator[UPSStatus]):
    """Share one status transaction between both entities."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=NAME,
            update_interval=timedelta(seconds=POLL_INTERVAL_SECONDS),
            always_update=False,
        )
        self.client = ArgonUPSClient(entry.data["port"])

    async def _async_update_data(self) -> UPSStatus:
        try:
            return await self.hass.async_add_executor_job(self.client.query)
        except ArgonUPSError as err:
            raise UpdateFailed(f"Cannot read Argon UPS: {err}") from err

    async def async_shutdown(self) -> None:
        """Stop timers and release the port on unload or Home Assistant shutdown."""
        await super().async_shutdown()
        await self.hass.async_add_executor_job(self.client.close)
