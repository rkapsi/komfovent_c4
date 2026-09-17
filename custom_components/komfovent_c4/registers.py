"""
Modbus register definitions for the Komfovent C4 controller.

Transcribed from ``docs/MODBUS_C4.pdf`` ("Modbus registers of C4 controller").

Every C4 register is a single 16-bit word -- there are no 32-bit register pairs
anywhere in the map, which is the main reason this integration is so much
simpler than the C6/C8 one.

Register numbers below are the 1-based numbers printed in the documentation.
``Register.address`` is the 0-based Modbus address actually put on the wire.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class Access(Enum):
    """Whether a register may be written."""

    READ_ONLY = "r"
    READ_WRITE = "rw"


class DataType(Enum):
    """
    How a register's 16-bit word is interpreted.

    ``BITFIELD`` is kept distinct from ``UINT16`` so that alarm registers are
    never accidentally coerced to a 0/1 flag -- their individual bits carry
    separate meanings.
    """

    INT16 = "int16"
    UINT16 = "uint16"
    BITFIELD = "bitfield"
    PACKED_BYTES = "packed_bytes"  # 2x char, e.g. 8:05 => 0x0805


class Register(Enum):
    """A Komfovent C4 holding register."""

    # -- General (1000-1013) ------------------------------------------------
    POWER = (1000, DataType.INT16, Access.READ_WRITE)
    SEASON = (1001, DataType.INT16, Access.READ_WRITE)
    TIME = (1002, DataType.PACKED_BYTES, Access.READ_WRITE)
    DAY_OF_WEEK = (1003, DataType.INT16, Access.READ_WRITE)
    MONTH_DAY = (1004, DataType.PACKED_BYTES, Access.READ_WRITE)
    YEAR = (1005, DataType.INT16, Access.READ_WRITE)
    MODBUS_ADDRESS = (1006, DataType.INT16, Access.READ_WRITE)
    ALARM_WARNINGS = (1007, DataType.BITFIELD, Access.READ_ONLY)
    ALARM_STOP_FLAGS = (1008, DataType.BITFIELD, Access.READ_ONLY)
    ALARM_STOP_CODE = (1009, DataType.INT16, Access.READ_ONLY)
    RECUPERATOR_LEVEL = (1010, DataType.INT16, Access.READ_ONLY)
    ELECTRIC_HEATER_LEVEL = (1011, DataType.INT16, Access.READ_ONLY)
    WATER_HEATING_LEVEL = (1012, DataType.INT16, Access.READ_ONLY)
    WATER_COOLING_LEVEL = (1013, DataType.INT16, Access.READ_ONLY)

    # -- Ventilation (1100-1116) -------------------------------------------
    VENTILATION_LEVEL_MANUAL = (1100, DataType.INT16, Access.READ_WRITE)
    VENTILATION_LEVEL_CURRENT = (1101, DataType.INT16, Access.READ_ONLY)
    OPERATION_MODE = (1102, DataType.INT16, Access.READ_WRITE)
    INTAKE_INTENSITY_1 = (1103, DataType.INT16, Access.READ_WRITE)
    INTAKE_INTENSITY_2 = (1104, DataType.INT16, Access.READ_WRITE)
    INTAKE_INTENSITY_3 = (1105, DataType.INT16, Access.READ_WRITE)
    INTAKE_INTENSITY_4 = (1106, DataType.INT16, Access.READ_WRITE)
    EXHAUST_INTENSITY_1 = (1107, DataType.INT16, Access.READ_WRITE)
    EXHAUST_INTENSITY_2 = (1108, DataType.INT16, Access.READ_WRITE)
    EXHAUST_INTENSITY_3 = (1109, DataType.INT16, Access.READ_WRITE)
    EXHAUST_INTENSITY_4 = (1110, DataType.INT16, Access.READ_WRITE)
    OVR_ENABLE = (1111, DataType.INT16, Access.READ_WRITE)
    OVR_TIME = (1112, DataType.INT16, Access.READ_WRITE)
    OVR_TIME_CURRENT = (1113, DataType.INT16, Access.READ_ONLY)
    AHU_FANS_STATUS = (1114, DataType.BITFIELD, Access.READ_ONLY)
    SUPPLY_FAN_LEVEL = (1115, DataType.INT16, Access.READ_ONLY)
    EXHAUST_FAN_LEVEL = (1116, DataType.INT16, Access.READ_ONLY)

    # -- Temperature (1200-1205) -------------------------------------------
    SUPPLY_AIR_TEMP = (1200, DataType.INT16, Access.READ_ONLY)
    SETPOINT_TEMP = (1201, DataType.INT16, Access.READ_WRITE)
    TEMP_CORRECTION = (1202, DataType.INT16, Access.READ_WRITE)
    TEMP_CORRECTION_START = (1203, DataType.PACKED_BYTES, Access.READ_WRITE)
    TEMP_CORRECTION_STOP = (1204, DataType.PACKED_BYTES, Access.READ_WRITE)
    WATER_TEMP = (1205, DataType.INT16, Access.READ_ONLY)

    number: int
    address: int
    datatype: DataType
    access: Access

    def __new__(cls, number: int, datatype: DataType, access: Access) -> Register:
        """Build a register member, deriving the 0-based Modbus address."""
        obj = object.__new__(cls)
        obj._value_ = number
        obj.number = number
        obj.address = number - 1
        obj.datatype = datatype
        obj.access = access
        return obj

    def __str__(self) -> str:
        """Return a readable name including the documented register number."""
        return f"{self.name}({self.number})"


BY_NUMBER: Final[dict[int, Register]] = {reg.number: reg for reg in Register}

# Contiguous runs polled in a single Modbus transaction. The C4 map has exactly
# three dense blocks (the schedule at 1300-1362 is deliberately not polled).
POLL_BLOCKS: Final[tuple[tuple[Register, int], ...]] = (
    (Register.POWER, 14),  # 1000-1013
    (Register.VENTILATION_LEVEL_MANUAL, 17),  # 1100-1116
    (Register.SUPPLY_AIR_TEMP, 6),  # 1200-1205
)
