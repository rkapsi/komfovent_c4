"""
Raw register dumping for the Komfovent C4.

This module deliberately imports nothing from Home Assistant and nothing from
the rest of this package, so that ``scripts/modbus_dump.py`` can load it by
file path on a machine that only has pymodbus installed.
"""

from __future__ import annotations

import logging

from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)

# Every documented block, including the schedule the integration does not poll.
# Keys are 1-based register numbers as printed in docs/MODBUS_C4.pdf.
DUMP_RANGES: tuple[tuple[int, int], ...] = (
    (1000, 14),  # general
    (1100, 17),  # ventilation
    (1200, 6),  # temperature
    (1300, 63),  # schedule
)


async def dump_registers(host: str, port: int) -> dict[int, list[int]]:
    """
    Read every documented register and return the raw words.

    The result is keyed by the 1-based number of the first register in each
    successfully read run, matching the fixture format ``scripts/modbus_server.py``
    consumes. A block that fails is retried one register at a time so that a
    single unreadable register does not hide the rest of its block.
    """
    client = AsyncModbusTcpClient(host=host, port=port)

    if not await client.connect():
        msg = f"Failed to connect to {host}:{port}"
        raise ConnectionError(msg)

    results: dict[int, list[int]] = {}
    try:
        for start, count in DUMP_RANGES:
            response = await client.read_holding_registers(
                address=start - 1, count=count
            )
            if not response.isError():
                results[start] = response.registers
                _LOGGER.info(
                    "Registers %d..%d: %s", start, start + count - 1, response.registers
                )
                continue

            _LOGGER.warning("Block read from %d failed, reading individually", start)
            for number in range(start, start + count):
                response = await client.read_holding_registers(
                    address=number - 1, count=1
                )
                if response.isError():
                    _LOGGER.warning("Register %d: read failed", number)
                    continue
                results[number] = response.registers
                _LOGGER.info("Register %d: %s", number, response.registers)
    finally:
        client.close()

    return results
