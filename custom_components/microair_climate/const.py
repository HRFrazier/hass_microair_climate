"""Constants for the MicroAir_EasyTouch integration."""

from datetime import timedelta
from enum import StrEnum

DOMAIN = "microair_climate"
REQUEST_TIMEOUT = 5
UPDATE_INTERVAL = timedelta(seconds=30)

ATTR_FAN_STATE = "fan_state"
ATTR_HVAC_STATE = "hvac_state"


class Commands(StrEnum):
    """Available Commands."""

    # add setpoint in HEX as two chars at the end.
    COMMAND_SET_SETPOINT_PREFIX = "17F0xx0004000000"

    COMMAND_SET_HVAC_MODE_OFF = "17F0xx000401000000"
    COMMAND_SET_HVAC_MODE_DRY = "17F0xx000402000000"
    COMMAND_SET_HVAC_MODE_AUTO = "17F0xx000403000000"
    COMMAND_SET_HVAC_MODE_HEAT = "17F0xx000404000000"
    COMMAND_SET_HVAC_MODE_COOL = "17F0xx000405000000"

    COMMAND_SET_FAN_MODE = "17F0xx0004000000"
