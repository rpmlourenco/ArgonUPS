"""Coordinate status polling and entity availability."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import ArgonUPSClient, ArgonUPSError
from .const import NAME, POLL_INTERVAL_SECONDS
from .protocol import DIAGNOSTIC_COMMANDS, DiagnosticReading, ReadCommand, UPSStatus

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
            # Publish successful polls even when values are unchanged so that
            # last_reported can be used to reject stale safety telemetry.
            always_update=True,
        )
        self.client = ArgonUPSClient(entry.data["port"])
        self.readings: dict[ReadCommand, DiagnosticReading | None] = dict.fromkeys(
            DIAGNOSTIC_COMMANDS
        )
        self._diagnostic_index = 0

    async def _async_update_data(self) -> UPSStatus:
        try:
            status = await self.hass.async_add_executor_job(self.client.query)
        except ArgonUPSError as err:
            self.readings = dict.fromkeys(DIAGNOSTIC_COMMANDS)
            raise UpdateFailed(f"Cannot read Argon UPS: {err}") from err
        # Only one optional transaction per cycle bounds its added delay to
        # one response timeout. Status is always queried first on the same port.
        command = DIAGNOSTIC_COMMANDS[self._diagnostic_index]
        self._diagnostic_index = (self._diagnostic_index + 1) % len(DIAGNOSTIC_COMMANDS)
        try:
            self.readings[command] = await self.hass.async_add_executor_job(
                self.client.query_diagnostic, command
            )
        except ArgonUPSError as err:
            self.readings[command] = None
            _LOGGER.debug("Optional UPS query %s failed: %s", command.name, err)
        return status

    async def async_shutdown(self) -> None:
        """Stop timers and release the port on unload or Home Assistant shutdown."""
        await super().async_shutdown()
        await self.hass.async_add_executor_job(self.client.close)
