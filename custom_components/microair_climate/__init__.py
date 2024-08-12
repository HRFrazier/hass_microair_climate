"""The MicroAir_EasyTouch integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MicroAirCoordinatorHub

PLATFORMS: list[Platform] = [Platform.CLIMATE]  # , Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up MicroAir_EasyTouch from a config entry."""

    # entry.runtime_data = MyAPI(...)

    # Setup coorninator and put it in the data section
    coordinator = MicroAirCoordinatorHub(
        hass, config.data[CONF_IP_ADDRESS], config.data[CONF_NAME]
    )
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class MicroAirEntity(CoordinatorEntity[MicroAirCoordinatorHub]):
    """Representation of a MicroAirTouch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        update_coordinator: MicroAirCoordinatorHub,
        config: ConfigEntry,
    ) -> None:
        """Initialize the data object."""
        super().__init__(update_coordinator)
        self._config = config
        self._coordinator = update_coordinator

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config.entry_id)},
            name=self._coordinator.name,
            manufacturer="MicroAir",
            model="MicroAir Easy Touch OEM",
            # sw_version="{}.{}".format(*(self._client.get_firmware_ver())),
        )
