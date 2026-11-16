"""Configure Argon UPS through the Home Assistant interface."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PORT

from .client import ArgonUPSError, probe
from .const import DEFAULT_PORT, DOMAIN, NAME


class ArgonUPSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate a direct serial port before creating an entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            if not port or "://" in port:
                errors[CONF_PORT] = "invalid_port"
            else:
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
                {vol.Required(CONF_PORT, default=DEFAULT_PORT): str}
            ),
            errors=errors,
        )
