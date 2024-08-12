"""MicroAir Data Coordinator."""

import asyncio.timeouts
import datetime
from datetime import timedelta
import logging

from defusedxml.ElementTree import fromstring
from requests import RequestException

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import Commands

_LOGGER = logging.getLogger(__name__)


class MicroAirCoordinatorHub(update_coordinator.DataUpdateCoordinator[None]):
    """Implementation of API."""

    def __init__(self, hass: HomeAssistant, ip_address: str, name: str) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=30),
        )

        self.last_update_success = False

        self._ip_addr = ip_address
        self._session = async_get_clientsession(hass)

        # Setup properties
        self._line_voltage = 240
        self._hvac_mode = HVACMode.OFF
        self._hvac_action = HVACAction.IDLE
        self._fan_state = FAN_OFF
        self._fan_mode = FAN_OFF
        self._setpoint = 0
        self._current_temp = 0
        self._current_humidity = 0
        self._my_network_id = ""

        self._next_setpoint_sync = datetime.datetime.now()
        self._handle_setpoint_sync = asyncio.create_task(
            self._async_desired_setpoint_push_delayed(False)
        )

    async def test_connection(self, ip_addr: str):
        """Test the connection to the thermostat by posting to get the status."""
        url = "http://" + ip_addr + "/ShortStatus"

        resp = await self._session.post(url)
        if resp.status != 200:
            self.last_update_success = False
            return False

        return True

    async def _async_transmit_data(self, cmd_string):
        try:
            url = "http://" + self._ip_addr + "/Transmission"
            final_cmd = cmd_string.replace("xx", self._my_network_id)
            resp = await self._session.post(url, data=final_cmd)
            if resp.status != 200:
                self.last_update_success = False
                return False

            x = await resp.content.read()
            content = x.decode("utf8")
            # print(content)
            success = "<X>OK</X>" in content
            if success:
                self.last_update_success = True
                _LOGGER.info(
                    "Successfully sent command %s to %s at device ID %s",
                    final_cmd,
                    self.name,
                    self._my_network_id,
                )
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during MicroAir Climate info update: {ex}"
            ) from ex

    async def _async_update_data(self) -> None:
        """Update the state."""
        _LOGGER.info("Updating state for %s", self.name)
        try:
            url = "http://" + self._ip_addr + "/ShortStatus"
            resp = await self._session.post(url)

            if resp.status != 200:
                self.last_update_success = False
                return

            x = await resp.content.read()
            content = x.decode("utf8")
            # print(content)
            await self.update_data_from_xml(content)
            self.last_update_success = True

        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during MicroAir Climate info update: {ex}"
            ) from ex

    async def force_update(self):
        """Update immediately."""
        await self._async_update_data()

    @property
    def hvac_mode(self):
        """Get the mode of the thermostat."""
        return self._hvac_mode

    @property
    def fan_mode(self):
        """Get the mode of the thermostat."""
        return self._fan_mode

    @property
    def setpoint(self):
        """Get the mode of the thermostat."""
        return self._setpoint

    @property
    def fanstate(self):
        """Get the mode of the thermostat."""
        return self._fan_state

    @property
    def hvac_action(self):
        """Get the run state of the thermostat."""
        return self._hvac_action

    @property
    def indoor_temp(self):
        """Get the temperature reading."""
        return self._current_temp

    @property
    def indoor_humidity(self):
        """Get the humidity reading."""
        return self._current_humidity

    @property
    def line_voltage(self):
        """Return the line voltage."""
        return self._line_voltage

    async def async_set_fan_mode(self, mode: str):
        """Set the fan mode, transmit update."""
        return

    async def async_set_hvac_mode(self, mode: HVACMode):
        """Make http call and set mode."""
        if mode == HVACMode.OFF:
            await self._async_transmit_data(Commands.COMMAND_SET_HVAC_MODE_OFF)
        elif mode == HVACMode.COOL:
            await self._async_transmit_data(Commands.COMMAND_SET_HVAC_MODE_COOL)
        elif mode == HVACMode.HEAT:
            await self._async_transmit_data(Commands.COMMAND_SET_HVAC_MODE_HEAT)
        elif mode == HVACMode.AUTO:
            await self._async_transmit_data(Commands.COMMAND_SET_HVAC_MODE_AUTO)
        elif mode == HVACMode.DRY:
            await self._async_transmit_data(Commands.COMMAND_SET_HVAC_MODE_DRY)

    async def update_data_from_xml(self, x):
        """Parse out xml and map properties."""
        xml = fromstring(x)
        data0 = xml[0].text
        data1 = xml[1].text
        # Get setpoint and temp
        self._setpoint = int(data0[16:18], 16)
        self._current_temp = int(data0[18:20], 16)
        self._line_voltage = int(data1[10:14], 16)
        # self._outside_temp = int(data0[])
        # print(self._line_voltage)
        # critical step. The thermostats talk to each other and assign a "Bus id"
        # or device id, between each other.
        self._my_network_id = data0[4:6]

        # print("Setpoint: %2d, Current Temp: %2d" % (self._setpoint, self._current_temp))

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
            self._hvac_action = HVACMode.OFF
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

    async def async_set_setpoint(self, setpoint):
        """Set the setpoint."""
        # Convert setpoint to hex and transmit setting string.
        self._setpoint = int(setpoint)
        self._next_setpoint_sync = datetime.datetime.now() + timedelta(seconds=2)
        if self._handle_setpoint_sync.done():
            self._handle_setpoint_sync = asyncio.create_task(
                self._async_desired_setpoint_push_delayed(True)
            )
        return True

    async def _async_desired_setpoint_push_delayed(self, actually_run):
        """Wait to send the setpoint to the thermostat in case user is pressing the plus or minus buttons."""
        if not actually_run:
            return

        while datetime.datetime.now() <= self._next_setpoint_sync:
            await asyncio.sleep(0.5)

        command = Commands.COMMAND_SET_SETPOINT_PREFIX + f"{self._setpoint:x}"
        await self._async_transmit_data(command)

    @property
    def setpoint_update_push_pending(self):
        """Return the state of the setpoint command wait/push."""
        return not self._handle_setpoint_sync.done()
