"""Config flow for MicroAir_EasyTouch integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MicroAirApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_DEVICE_INFO_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


class MicroAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MicroAir_EasyTouch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
            )
            api = MicroAirApi(
                async_get_clientsession(self.hass), user_input[CONF_IP_ADDRESS]
            )
            try:
                await api.async_get_status()
            except (ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_DEVICE_INFO_SCHEMA, errors=errors
        )
