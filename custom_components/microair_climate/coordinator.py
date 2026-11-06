"""MicroAir Data Coordinator."""

from __future__ import annotations

import logging
from xml.etree.ElementTree import ParseError

from aiohttp import ClientError
from defusedxml.ElementTree import fromstring

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    FAN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MicroAirApi
from .const import SETPOINT_DEBOUNCE_SECONDS, UPDATE_INTERVAL, Commands

_LOGGER = logging.getLogger(__name__)

type MicroAirConfigEntry = ConfigEntry[MicroAirCoordinatorHub]

HVAC_MODE_COMMANDS = {
    HVACMode.OFF: Commands.COMMAND_SET_HVAC_MODE_OFF,
    HVACMode.COOL: Commands.COMMAND_SET_HVAC_MODE_COOL,
    HVACMode.HEAT: Commands.COMMAND_SET_HVAC_MODE_HEAT,
    HVACMode.AUTO: Commands.COMMAND_SET_HVAC_MODE_AUTO,
    HVACMode.DRY: Commands.COMMAND_SET_HVAC_MODE_DRY,
}


class MicroAirCoordinatorHub(DataUpdateCoordinator[None]):
    """Polls the thermostat and holds its decoded state."""

    config_entry: MicroAirConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MicroAirConfigEntry,
        api: MicroAirApi,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.data[CONF_NAME],
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

        self._line_voltage = 240
        self._hvac_mode = HVACMode.OFF
        self._hvac_action = HVACAction.IDLE
        self._fan_state = FAN_OFF
        self._fan_mode = FAN_OFF
        self._setpoint = 0
        self._current_temp = 0
        self._current_humidity = 0
        self._my_network_id = ""

        self._setpoint_pending = False
        self._setpoint_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=SETPOINT_DEBOUNCE_SECONDS,
            immediate=False,
            function=self._async_push_setpoint,
        )

    async def async_shutdown(self) -> None:
        """Cancel any pending setpoint push."""
        await super().async_shutdown()
        self._setpoint_debouncer.async_cancel()

    async def _async_transmit_data(self, cmd_string: str) -> None:
        final_cmd = cmd_string.replace("xx", self._my_network_id)
        try:
            success = await self.api.async_transmit(final_cmd)
        except (ClientError, TimeoutError) as ex:
            raise HomeAssistantError(
                f"Error sending command to {self.name}: {ex}"
            ) from ex
        if not success:
            raise HomeAssistantError(f"{self.name} did not acknowledge {final_cmd}")
        _LOGGER.debug(
            "Successfully sent command %s to %s at device ID %s",
            final_cmd,
            self.name,
            self._my_network_id,
        )

    async def _async_update_data(self) -> None:
        """Fetch and decode the thermostat state."""
        try:
            content = await self.api.async_get_status()
        except (ClientError, TimeoutError) as ex:
            raise UpdateFailed(f"Error communicating with {self.name}: {ex}") from ex

        try:
            self._update_data_from_xml(content)
        except (ParseError, IndexError, TypeError, ValueError) as ex:
            raise UpdateFailed(f"Unexpected status payload from {self.name}") from ex

    @property
    def hvac_mode(self) -> HVACMode:
        """Get the mode of the thermostat."""
        return self._hvac_mode

    @property
    def fan_mode(self) -> str:
        """Get the fan mode of the thermostat."""
        return self._fan_mode

    @property
    def setpoint(self) -> int:
        """Get the setpoint of the thermostat."""
        return self._setpoint

    @property
    def fanstate(self) -> str:
        """Get the fan speed of the thermostat."""
        return self._fan_state

    @property
    def hvac_action(self) -> HVACAction:
        """Get the run state of the thermostat."""
        return self._hvac_action

    @property
    def indoor_temp(self) -> int:
        """Get the temperature reading."""
        return self._current_temp

    @property
    def indoor_humidity(self) -> int:
        """Get the humidity reading."""
        return self._current_humidity

    @property
    def line_voltage(self) -> int:
        """Return the line voltage."""
        return self._line_voltage

    async def async_set_fan_mode(self, mode: str) -> bool:
        """Set the fan mode, transmit update."""
        return False

    async def async_set_hvac_mode(self, mode: HVACMode) -> None:
        """Make http call and set mode."""
        if command := HVAC_MODE_COMMANDS.get(mode):
            await self._async_transmit_data(command)

    def _update_data_from_xml(self, x: str) -> None:
        """Parse out xml and map properties."""
        xml = fromstring(x)
        data0 = xml[0].text
        data1 = xml[1].text
        # Get setpoint and temp
        if not self._setpoint_pending:
            self._setpoint = int(data0[16:18], 16)
        self._current_temp = int(data0[18:20], 16)
        self._line_voltage = int(data1[10:14], 16)
        # self._outside_temp = int(data0[])
        # critical step. The thermostats talk to each other and assign a "Bus id"
        # or device id, between each other.
        self._my_network_id = data0[4:6]

        controlMode = int(data0[11:13], 16)
        if controlMode == 0:
            self._hvac_mode = HVACMode.OFF
        elif controlMode == 48:
            self._hvac_mode = HVACMode.AUTO
        elif controlMode == 80:
            self._hvac_mode = HVACMode.COOL
        elif controlMode == 64:
            self._hvac_mode = HVACMode.HEAT
        elif controlMode == 32:
            self._hvac_mode = HVACMode.DRY

        statusBits = int(data0[12:14], 16)

        compressorStatus = bool(statusBits & 0b010)
        # fanstate = bool(statusBits & 0b100)

        if self._hvac_mode == HVACMode.OFF:
            self._hvac_action = HVACAction.OFF
        elif self._hvac_mode == HVACMode.COOL:
            if compressorStatus:
                self._hvac_action = HVACAction.COOLING
            else:
                self._hvac_action = HVACAction.IDLE
        elif self._hvac_mode == HVACMode.HEAT:
            if compressorStatus:
                self._hvac_action = HVACAction.HEATING
            else:
                self._hvac_action = HVACAction.IDLE
        elif self._hvac_mode == HVACMode.DRY:
            if compressorStatus:
                self._hvac_action = HVACAction.DRYING
            else:
                self._hvac_action = HVACAction.IDLE
        elif self._hvac_mode == HVACMode.AUTO:
            if compressorStatus:
                if self.setpoint < self.indoor_temp:
                    self._hvac_action = HVACAction.COOLING
                else:
                    self._hvac_action = HVACAction.HEATING
            else:
                self._hvac_action = HVACAction.IDLE

        # Get fan mode
        fanMode = int(data0[15:16], 16)
        if fanMode == 0:
            self._fan_state = FAN_OFF
            self._fan_mode = FAN_OFF
        elif fanMode == 1:
            self._fan_state = FAN_LOW
            self._fan_mode = FAN_ON
        elif fanMode == 2:
            self._fan_state = FAN_MEDIUM
            self._fan_mode = FAN_ON
        elif fanMode == 3:
            self._fan_state = FAN_HIGH
            self._fan_mode = FAN_AUTO
        elif fanMode == 8:
            self._fan_state = FAN_LOW
            self._fan_mode = FAN_AUTO
        elif fanMode == 9:
            self._fan_state = FAN_MEDIUM
            self._fan_mode = FAN_AUTO
        elif fanMode == 10:
            self._fan_state = FAN_HIGH
            self._fan_mode = FAN_AUTO

    async def async_set_setpoint(self, setpoint: float) -> None:
        """Store the setpoint and push it once the user stops adjusting it."""
        self._setpoint = int(setpoint)
        self._setpoint_pending = True
        await self._setpoint_debouncer.async_call()

    async def _async_push_setpoint(self) -> None:
        """Send the setpoint to the thermostat and refresh its state."""
        try:
            await self._async_transmit_data(
                Commands.COMMAND_SET_SETPOINT_PREFIX + f"{self._setpoint:x}"
            )
        finally:
            self._setpoint_pending = False
        await self.async_request_refresh()
