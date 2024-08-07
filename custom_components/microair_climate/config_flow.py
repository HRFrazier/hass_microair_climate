"""Config flow for MicroAir_EasyTouch integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import MicroAirCoordinatorHub

_LOGGER = logging.getLogger(__name__)

STEP_DEVICE_INFO_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )

    hub = MicroAirCoordinatorHub(hass, data[CONF_IP_ADDRESS], data[CONF_NAME])

    if not await hub.test_connection(data[CONF_IP_ADDRESS]):
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"device_name": data[CONF_NAME], "ip_address": data[CONF_IP_ADDRESS]}


class MicroAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MicroAir_EasyTouch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["device_name"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_DEVICE_INFO_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
