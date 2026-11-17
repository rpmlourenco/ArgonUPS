"""Coordinate status polling and entity availability."""

import logging
from datetime import UTC, datetime, timedelta

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
        self.diagnostic_details = {
            command: {"query_status": "waiting_for_first_query"}
            for command in DIAGNOSTIC_COMMANDS
        }
        self._diagnostic_failures: dict[ReadCommand, tuple[str, str]] = {}

    async def _async_update_data(self) -> UPSStatus:
        try:
            status = await self.hass.async_add_executor_job(self.client.query)
        except ArgonUPSError as err:
            self.readings = dict.fromkeys(DIAGNOSTIC_COMMANDS)
            self.diagnostic_details = {
                command: {"query_status": "status_unavailable"}
                for command in DIAGNOSTIC_COMMANDS
            }
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
            self.diagnostic_details[command] = {
                "query_status": err.reason,
                "last_error": str(err),
                "last_query_time": datetime.now(UTC).isoformat(),
                "raw_response": err.raw_response.hex(" "),
            }
            if err.response_payload is not None:
                self.diagnostic_details[command]["raw_payload"] = (
                    err.response_payload.hex(" ")
                )
            failure = (err.reason, str(err))
            if self._diagnostic_failures.get(command) != failure:
                _LOGGER.warning(
                    "UPS diagnostic %s failed (%s): %s; payload=%s; received=%s",
                    command.name,
                    err.reason,
                    err,
                    err.response_payload.hex(" ")
                    if err.response_payload is not None
                    else "none",
                    err.raw_response.hex(" ") or "none",
                )
            self._diagnostic_failures[command] = failure
        else:
            self.diagnostic_details[command] = {
                "query_status": "ok",
                "last_query_time": datetime.now(UTC).isoformat(),
            }
            if self._diagnostic_failures.pop(command, None) is not None:
                _LOGGER.info("UPS diagnostic %s recovered", command.name)
        return status

    async def async_shutdown(self) -> None:
        """Stop timers and release the port on unload or Home Assistant shutdown."""
        await super().async_shutdown()
        await self.hass.async_add_executor_job(self.client.close)
