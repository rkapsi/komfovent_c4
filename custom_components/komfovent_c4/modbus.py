"""Modbus TCP client for the Komfovent C4 controller."""

from __future__ import annotations

import asyncio
import logging

from pymodbus import ModbusException
from pymodbus.client import AsyncModbusTcpClient

from .registers import BY_NUMBER, Access, DataType, Register

_LOGGER = logging.getLogger(__name__)

_SIGN_BIT = 15


def decode(datatype: DataType, word: int) -> int:
    """Decode a raw 16-bit word according to the register's data type."""
    if datatype == DataType.INT16:
        return word - (word >> _SIGN_BIT << 16)
    return word


def encode(datatype: DataType, value: int) -> int:
    """Encode a value into the raw 16-bit word written to the device."""
    if datatype == DataType.INT16:
        return value & 0xFFFF
    return value


class KomfoventC4Client:
    """Reads and writes C4 holding registers over Modbus TCP."""

    def __init__(self, host: str, port: int = 502) -> None:
        """Initialize the Modbus client."""
        self.client = AsyncModbusTcpClient(
            host=host,
            port=port,
            timeout=10,
            retries=3,
            reconnect_delay=5,
            reconnect_delay_max=60,
        )
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to the device."""
        return await self.client.connect()

    def close(self) -> None:
        """Close the connection."""
        self.client.close()

    async def read_words(self, number: int, count: int) -> list[int]:
        """
        Read ``count`` raw words starting at documented register ``number``.

        The words are returned undecoded, in wire order. This is for the parts
        of the map without ``Register`` members, i.e. the weekly schedule.
        """
        async with self._lock:
            result = await self.client.read_holding_registers(
                address=number - 1, count=count
            )

        if result.isError():
            msg = f"Error reading {count} registers from {number}"
            raise ModbusException(msg)
        return list(result.registers)

    async def read_block(self, start: Register, count: int) -> dict[Register, int]:
        """
        Read ``count`` consecutive registers in a single transaction.

        Words that do not correspond to a documented register are skipped, so a
        block may span small gaps in the register map.
        """
        words = await self.read_words(start.number, count)

        data: dict[Register, int] = {}
        for offset, word in enumerate(words):
            register = BY_NUMBER.get(start.number + offset)
            if register is not None:
                data[register] = decode(register.datatype, word)
        return data

    async def read(self, register: Register) -> int | None:
        """Read a single register."""
        return (await self.read_block(register, 1)).get(register)

    async def write(self, register: Register, value: int) -> None:
        """Write a single register."""
        if register.access == Access.READ_ONLY:
            msg = f"{register} is read-only"
            raise ModbusException(msg)

        async with self._lock:
            result = await self.client.write_register(
                address=register.address, value=encode(register.datatype, value)
            )

        if result.isError():
            msg = f"Error writing {register}"
            raise ModbusException(msg)
