"""The MicroAir_EasyTouch integration."""

from __future__ import annotations

from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MicroAirApi
from .coordinator import MicroAirConfigEntry, MicroAirCoordinatorHub

PLATFORMS: list[Platform] = [Platform.CLIMATE]  # , Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MicroAirConfigEntry) -> bool:
    """Set up MicroAir_EasyTouch from a config entry."""
    api = MicroAirApi(async_get_clientsession(hass), entry.data[CONF_IP_ADDRESS])
    coordinator = MicroAirCoordinatorHub(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MicroAirConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
