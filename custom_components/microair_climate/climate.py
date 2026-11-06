"""Support for MicroAir WiFi Thermostats."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_OFF,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_FAN_STATE, ATTR_HVAC_STATE
from .coordinator import MicroAirConfigEntry, MicroAirCoordinatorHub
from .entity import MicroAirEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MicroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MicroAir thermostat."""
    async_add_entities([MicroAirThermostat(config_entry.runtime_data)])


class MicroAirThermostat(MicroAirEntity, ClimateEntity):
    """Representation of a MicroAir thermostat."""

    _attr_fan_modes = [FAN_OFF, FAN_ON, FAN_AUTO]
    _attr_hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.DRY,
    ]
    _attr_precision = PRECISION_WHOLE
    _attr_name = None
    _attr_min_temp = 70
    _attr_max_temp = 85
    _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: MicroAirCoordinatorHub) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def native_current_temperature(self) -> int:
        """Return the current temperature."""
        return self.coordinator.indoor_temp

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self.coordinator.indoor_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode ie. heat, cool, auto."""
        return self.coordinator.hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running action ie. heating, cooling, idle."""
        return self.coordinator.hvac_action

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self.coordinator.fan_mode

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the optional state attributes."""
        return {
            ATTR_FAN_STATE: self.coordinator.fanstate,
            ATTR_HVAC_STATE: self.coordinator.hvac_action,
        }

    @property
    def native_target_temperature(self) -> int:
        """Return the target temperature we try to reach."""
        return self.coordinator.setpoint

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.async_set_setpoint(temperature)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == FAN_ON:
            success = await self.coordinator.async_set_fan_mode(FAN_HIGH)
        else:
            success = await self.coordinator.async_set_fan_mode(FAN_AUTO)

        if not success:
            _LOGGER.error("Failed to change the fan mode")
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.coordinator.async_set_hvac_mode(hvac_mode)
        await self.coordinator.async_request_refresh()
