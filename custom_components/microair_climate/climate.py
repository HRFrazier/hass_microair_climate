"""Support for MicroAir WiFi Thermostats."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRECISION_WHOLE,
    STATE_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MicroAirEntity
from .const import ATTR_FAN_STATE, ATTR_HVAC_STATE, DOMAIN
from .coordinator import MicroAirCoordinatorHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MicroAir thermostat."""
    MicroAirDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            MicroAirThermostat(
                MicroAirDataUpdateCoordinator,
                config_entry,
            )
        ],
    )


class MicroAirThermostat(MicroAirEntity, ClimateEntity):
    """Representation of a MicroAir thermostat."""

    _attr_fan_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO, FAN_OFF]
    _attr_hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.DRY,
    ]
    _attr_preset_modes = []
    _attr_precision = PRECISION_WHOLE
    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False
    _attr_min_temp = 70
    _attr_max_temp = 85

    def __init__(
        self,
        coordinator: MicroAirCoordinatorHub,
        config: ConfigEntry,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator, config)
        self._attr_unique_id = config.entry_id
        self._taskhandle_delayed_update = asyncio.create_task(
            self._async_desired_setpoint_push_delayed(True)
        )
        # self._mode_map = {
        #     HVACMode.HEAT: self.coordinator.MODE_HEAT,
        #     HVACMode.COOL: self.coordinator.MODE_COOL,
        #     HVACMode.AUTO: self.coordinator.MODE_AUTO,
        #     HVACMode.DRY: self.coordinator.MODE_DRY,
        # }

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        if self._coordinator.hvac_mode == HVACMode.AUTO:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        return features

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement, as defined by the API."""
        # if self._coordinator.tempunits == self._coordinator.TEMPUNITS_F:
        #    return UnitOfTemperature.FAHRENHEIT
        # return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> int:
        """Return the current temperature."""
        return self._coordinator.indoor_temp

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._coordinator.indoor_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode ie. heat, cool, auto."""
        return self._coordinator.hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return current operation mode ie. heat, cool, auto."""
        return self._coordinator.hvac_action

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self._coordinator.fan_mode

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the optional state attributes."""
        return {
            ATTR_FAN_STATE: self._coordinator.fanstate,
            ATTR_HVAC_STATE: self._coordinator.hvac_action,
        }

    @property
    def target_temperature(self) -> int:
        """Return the target temperature we try to reach."""
        return self._coordinator.setpoint

    async def async_set_operation_mode(self, operation_mode: HVACMode):
        """Change the operation mode (internal)."""
        success = await self._coordinator.async_set_hvac_mode(operation_mode)
        if not success:
            _LOGGER.error("Failed to change the operation mode")
        self.schedule_update_ha_state(force_refresh=True)
        return success

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.coordinator.async_set_setpoint(temperature)
        if self._taskhandle_delayed_update.done():
            _LOGGER.info("Triggering an update for %s", self.name)
            self._taskhandle_delayed_update = asyncio.create_task(
                self._async_desired_setpoint_push_delayed(True)
            )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == STATE_ON:
            success = await self._coordinator.async_set_fan_mode(FAN_HIGH)
        else:
            success = await self._coordinator.async_set_fan_mode(FAN_AUTO)

        if not success:
            _LOGGER.error("Failed to change the fan mode")
        self.schedule_update_ha_state(force_refresh=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.coordinator.async_set_hvac_mode(hvac_mode)
        self.schedule_update_ha_state(force_refresh=True)

    async def _async_desired_setpoint_push_delayed(self, actually_run):
        """Wait for coordinator to push setpoint before updating from the thermostat."""
        if not actually_run:
            return
        while self.coordinator.setpoint_update_push_pending:
            await asyncio.sleep(0.5)
        _LOGGER.info("Triggering an update for %s", self.name)
        self.schedule_update_ha_state(force_refresh=True)
