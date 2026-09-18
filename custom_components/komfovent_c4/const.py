"""Constants for the Komfovent C4 integration."""

from __future__ import annotations

from enum import IntEnum
from typing import Final

DOMAIN: Final = "komfovent_c4"
MANUFACTURER: Final = "Komfovent"
MODEL: Final = "C4"

DEFAULT_NAME: Final = "Komfovent C4"
DEFAULT_PORT: Final = 502

# Options
OPT_UPDATE_INTERVAL: Final = "update_interval"
DEFAULT_UPDATE_INTERVAL: Final = 30  # seconds

# Setpoint bounds, register 1201 is documented as 0..300 (0.0-30.0 C)
# A temperature register reads 0x7FFF when its sensor is not fitted; observed on
# register 1205 (water temp) of a unit with an electric heater and no water coil.
TEMP_NO_SENSOR: Final = 0x7FFF

SETPOINT_MIN_TEMP: Final = 0.0
SETPOINT_MAX_TEMP: Final = 30.0
SETPOINT_STEP_TEMP: Final = 0.1

# Temperature correction, register 1202 is documented as -90..+90 (-9.0-+9.0 C)
CORRECTION_MIN_TEMP: Final = -9.0
CORRECTION_MAX_TEMP: Final = 9.0

# Boost ("OVR") duration, register 1112 is documented as 1..90 minutes
OVR_TIME_MIN: Final = 1
OVR_TIME_MAX: Final = 90

# Fan intensity, registers 1103-1110 are documented as 0 or 20..100 percent
INTENSITY_MIN: Final = 20
INTENSITY_MAX: Final = 100


class Season(IntEnum):
    """Register 1001 -- heating/cooling season."""

    SUMMER = 0
    WINTER = 1


class OperationMode(IntEnum):
    """Register 1102 -- whether the weekly schedule drives the fan level."""

    MANUAL = 0
    AUTO = 1


class VentilationLevel(IntEnum):
    """Register 1100 -- the manually selected fan level."""

    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class StopCode(IntEnum):
    """Register 1009 -- the reason the unit stopped itself."""

    NONE = 0
    ROTOR_STOP = 3
    HEATER_OVERHEATING = 4
    SUPPLY_SENSOR_B1 = 9
    AIR_TEMP_LOW = 19
    AIR_TEMP_HIGH = 20
    WATER_TEMP_LOW = 27
    FROST_POSSIBILITY = 28


# Register 1007 bit positions, per "14-Service, 13-Heater off, 11-Rotor stop".
WARNING_BITS: Final[dict[str, int]] = {
    "rotor_stop": 11,
    "heater_off": 13,
    "service": 14,
}

# Register 1008 bit positions, per the numbered list in the documentation.
STOP_FLAG_BITS: Final[dict[str, int]] = {
    "supply_sensor_b1": 1,
    "heater_overheating": 2,
    "water_temp_low": 3,
    "rotor_stop": 4,
    "frost_possibility": 5,
    "air_temp_high": 6,
    "air_temp_low": 7,
}
