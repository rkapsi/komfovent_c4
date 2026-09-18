"""
Tests that drive the real client against a simulated C4 over a real socket.

Unlike the mocked tests these exercise pymodbus framing and the documented
register-number-to-address offset end to end.

    uv run pytest tests/test_live_modbus.py -v
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
from custom_components.komfovent_c4.dump import dump_registers
from custom_components.komfovent_c4.modbus import KomfoventC4Client
from custom_components.komfovent_c4.registers import POLL_BLOCKS, DataType, Register
from scripts.modbus_server import run_server

FIXTURES = Path(__file__).parent / "fixtures"
SYNTHETIC = FIXTURES / "C4_registers_synthetic.json"
REAL = FIXTURES / "C4_registers_mine.json"


@pytest.fixture(params=[SYNTHETIC, REAL], ids=["synthetic", "real"])
def register_dump(request) -> dict[str, list[int]]:
    """Load a register dump; the live tests run once per fixture file."""
    with request.param.open() as f:
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


def _decoded(dump: dict[str, list[int]], register: Register) -> int:
    """Look a register up in the dump and apply the client's int16 decoding."""
    raw = _expected(dump, register)
    if register.datatype is DataType.INT16 and raw >= 0x8000:
        return raw - 0x10000
    return raw


@pytest.mark.enable_socket
async def test_client_reads_every_poll_block(simulator, register_dump):
    client = KomfoventC4Client("127.0.0.1", simulator)
    try:
        assert await client.connect()

        data: dict[Register, int] = {}
        for start, count in POLL_BLOCKS:
            data.update(await client.read_block(start, count))

        assert set(data) == set(Register)
        for register in Register:
            assert data[register] == _decoded(register_dump, register), register
        # Off-by-one guard: 1205 must not come back with 1203's value.
        assert data[Register.WATER_TEMP] != _expected(
            register_dump, Register.TEMP_CORRECTION_START
        )
    finally:
        client.close()


@pytest.mark.enable_socket
@pytest.mark.parametrize("register_dump", [SYNTHETIC], indirect=True)
async def test_client_decodes_negative_int16_over_the_wire(simulator):
    """Only the synthetic dump carries a negative correction (-2.5 C)."""
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
            assert coordinator.data[register] == _decoded(register_dump, register), (
                register
            )
    finally:
        coordinator.client.close()


@pytest.mark.enable_socket
async def test_dump_registers_roundtrips_fixture(simulator, register_dump):
    """Dumping the simulator must reproduce the fixture it was started from."""
    dumped = await dump_registers("127.0.0.1", simulator)
    assert {str(k): v for k, v in dumped.items()} == register_dump


@pytest.mark.enable_socket
@pytest.mark.parametrize("register_dump", [SYNTHETIC], indirect=True)
async def test_dump_registers_skips_unreadable_block(register_dump):
    """A block the unit rejects falls back to single reads and is then skipped."""
    partial = {k: v for k, v in register_dump.items() if k != "1300"}
    port = random.randint(1024, 50000)
    task = asyncio.create_task(run_server("127.0.0.1", port, partial))
    await asyncio.sleep(0.1)
    try:
        dumped = await dump_registers("127.0.0.1", port)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert set(dumped) == {1000, 1100, 1200}


@pytest.mark.enable_socket
async def test_dump_registers_raises_when_unreachable():
    with pytest.raises(ConnectionError):
        await dump_registers("127.0.0.1", 1)
