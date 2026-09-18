"""Tests for the Modbus client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus import ModbusException

from custom_components.komfovent_c4.modbus import (
    KomfoventC4Client,
    decode,
    encode,
)
from custom_components.komfovent_c4.registers import DataType, Register


@pytest.fixture
def client():
    with patch("custom_components.komfovent_c4.modbus.AsyncModbusTcpClient"):
        yield KomfoventC4Client("192.0.2.10")


def _response(*words: int, error: bool = False):
    result = MagicMock()
    result.isError.return_value = error
    result.registers = list(words)
    return result


@pytest.mark.parametrize(
    ("datatype", "word", "expected"),
    [
        (DataType.INT16, 250, 250),
        (DataType.INT16, 0xFFFF, -1),  # -0.1 C
        (DataType.INT16, 0xFFA6, -90),  # -9.0 C, the correction minimum
        (DataType.UINT16, 0xFFFF, 0xFFFF),
        (DataType.BITFIELD, 0x4000, 0x4000),  # bit 14, must not become 1
        (DataType.PACKED_BYTES, 0x0805, 0x0805),  # 8:05
    ],
)
def test_decode(datatype, word, expected):
    assert decode(datatype, word) == expected


@pytest.mark.parametrize(
    ("datatype", "value", "expected"),
    [
        (DataType.INT16, 250, 250),
        (DataType.INT16, -1, 0xFFFF),
        (DataType.INT16, -90, 0xFFA6),
        (DataType.UINT16, 0x0805, 0x0805),
    ],
)
def test_encode(datatype, value, expected):
    assert encode(datatype, value) == expected


def test_decode_encode_roundtrip_negative():
    assert decode(DataType.INT16, encode(DataType.INT16, -90)) == -90


async def test_read_block_maps_words_to_registers(client):
    client.client.read_holding_registers = AsyncMock(
        return_value=_response(250, 200, 0xFFA6, 0x0805, 0x1000, 150)
    )

    data = await client.read_block(Register.SUPPLY_AIR_TEMP, 6)

    client.client.read_holding_registers.assert_awaited_once_with(address=1199, count=6)
    assert data[Register.SUPPLY_AIR_TEMP] == 250
    assert data[Register.SETPOINT_TEMP] == 200
    assert data[Register.TEMP_CORRECTION] == -90
    assert data[Register.TEMP_CORRECTION_START] == 0x0805
    assert data[Register.WATER_TEMP] == 150


async def test_read_block_preserves_alarm_bits(client):
    """A bitfield register must not be collapsed to a 0/1 flag."""
    client.client.read_holding_registers = AsyncMock(
        return_value=_response(0x6800)  # bits 14, 13 and 11
    )

    data = await client.read_block(Register.ALARM_WARNINGS, 1)

    assert data[Register.ALARM_WARNINGS] == 0x6800


async def test_read_block_skips_undocumented_words(client):
    """Words with no matching register are dropped rather than misattributed."""
    client.client.read_holding_registers = AsyncMock(
        return_value=_response(*([0] * 20))
    )

    data = await client.read_block(Register.SUPPLY_AIR_TEMP, 20)

    assert set(data) == {
        Register.SUPPLY_AIR_TEMP,
        Register.SETPOINT_TEMP,
        Register.TEMP_CORRECTION,
        Register.TEMP_CORRECTION_START,
        Register.TEMP_CORRECTION_STOP,
        Register.WATER_TEMP,
    }


async def test_read_block_raises_on_error(client):
    client.client.read_holding_registers = AsyncMock(return_value=_response(error=True))

    with pytest.raises(ModbusException):
        await client.read_block(Register.POWER, 14)


async def test_read_single(client):
    client.client.read_holding_registers = AsyncMock(return_value=_response(1))

    assert await client.read(Register.POWER) == 1


async def test_write_uses_zero_based_address(client):
    client.client.write_register = AsyncMock(return_value=_response())

    await client.write(Register.SETPOINT_TEMP, 205)

    client.client.write_register.assert_awaited_once_with(address=1200, value=205)


async def test_write_encodes_negative_values(client):
    client.client.write_register = AsyncMock(return_value=_response())

    await client.write(Register.TEMP_CORRECTION, -90)

    client.client.write_register.assert_awaited_once_with(address=1201, value=0xFFA6)


async def test_write_rejects_read_only_register(client):
    client.client.write_register = AsyncMock()

    with pytest.raises(ModbusException, match="read-only"):
        await client.write(Register.SUPPLY_AIR_TEMP, 1)

    client.client.write_register.assert_not_awaited()


async def test_write_raises_on_error(client):
    client.client.write_register = AsyncMock(return_value=_response(error=True))

    with pytest.raises(ModbusException):
        await client.write(Register.POWER, 1)
