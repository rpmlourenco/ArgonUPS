"""Configure Argon UPS through the Home Assistant interface."""

import voluptuous as vol
from homeassistant.components import usb
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .client import ArgonUPSError, probe
from .const import DEFAULT_PORT, DOMAIN, NAME


class ArgonUPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate a direct serial port before creating an entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._default_port = DEFAULT_PORT

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Offer setup after passive discovery, without querying the device yet."""
        self._default_port = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )
        await self.async_set_unique_id(self._default_port)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": NAME}
        return await self.async_step_user()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            if not port or "://" in port:
                errors[CONF_PORT] = "invalid_port"
            else:
                port = await self.hass.async_add_executor_job(
                    usb.get_serial_by_id, port
                )
                self._default_port = port
                await self.async_set_unique_id(port)
                self._abort_if_unique_id_configured()
                try:
                    await self.hass.async_add_executor_job(probe, port)
                except ArgonUPSError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=NAME, data={CONF_PORT: port})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PORT, default=self._default_port): str}
            ),
            errors=errors,
        )
