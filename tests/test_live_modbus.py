"""
Tests that drive the real client against a simulated C4 over a real socket.

Unlike the mocked tests these exercise pymodbus framing and the documented
register-number-to-address offset end to end.

    uv run pytest tests/test_live_modbus.py -v --socket-enabled
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from pathlib import Path

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.komfovent_c4.const import DOMAIN
from custom_components.komfovent_c4.coordinator import KomfoventC4Coordinator
from custom_components.komfovent_c4.modbus import KomfoventC4Client
from custom_components.komfovent_c4.registers import POLL_BLOCKS, Register
from scripts.modbus_server import run_server

FIXTURE = Path(__file__).parent / "fixtures" / "C4_registers_synthetic.json"


@pytest.fixture
def register_dump() -> dict[str, list[int]]:
    with FIXTURE.open() as f:
        return json.load(f)


@pytest.fixture
async def simulator(register_dump):
    """Start the simulator on a random port and yield (port, dump)."""
    port = random.randint(1024, 50000)
    task = asyncio.create_task(run_server("127.0.0.1", port, register_dump))
    await asyncio.sleep(0.1)
    try:
        yield port
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def _expected(dump: dict[str, list[int]], register: Register) -> int:
    """Look a register's raw word up in the dump."""
    for start, words in dump.items():
        offset = register.number - int(start)
        if 0 <= offset < len(words):
            return words[offset]
    msg = f"{register} not in fixture"
    raise KeyError(msg)


@pytest.mark.enable_socket
async def test_client_reads_every_poll_block(simulator, register_dump):
    client = KomfoventC4Client("127.0.0.1", simulator)
    try:
        assert await client.connect()

        data: dict[Register, int] = {}
        for start, count in POLL_BLOCKS:
            data.update(await client.read_block(start, count))

        assert set(data) == set(Register)
        assert data[Register.POWER] == 1
        assert data[Register.SETPOINT_TEMP] == 200
        assert data[Register.WATER_TEMP] == 450
        # Off-by-one guard: 1205 must not come back with 1203's value.
        assert data[Register.WATER_TEMP] != _expected(
            register_dump, Register.TEMP_CORRECTION_START
        )
    finally:
        client.close()


@pytest.mark.enable_socket
async def test_client_decodes_negative_int16_over_the_wire(simulator):
    client = KomfoventC4Client("127.0.0.1", simulator)
    try:
        await client.connect()
        assert await client.read(Register.TEMP_CORRECTION) == -25
    finally:
        client.close()


@pytest.mark.enable_socket
async def test_client_write_roundtrip(simulator):
    client = KomfoventC4Client("127.0.0.1", simulator)
    try:
        await client.connect()

        await client.write(Register.SETPOINT_TEMP, 215)
        assert await client.read(Register.SETPOINT_TEMP) == 215

        await client.write(Register.TEMP_CORRECTION, -90)
        assert await client.read(Register.TEMP_CORRECTION) == -90
    finally:
        client.close()


@pytest.mark.enable_socket
async def test_coordinator_against_simulator(hass, simulator, register_dump):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: simulator},
        entry_id="live",
    )
    coordinator = KomfoventC4Coordinator(hass, config_entry=entry)
    try:
        await coordinator.connect()
        await coordinator.async_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data) == len(list(Register))
        for register in Register:
            raw = _expected(register_dump, register)
            expected = raw - 0x10000 if raw >= 0x8000 and register.datatype.value == "int16" else raw
            assert coordinator.data[register] == expected, register
    finally:
        coordinator.client.close()
