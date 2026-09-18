#!/usr/bin/env python3
"""
Modbus TCP server simulating a Komfovent C4 from a register dump.

    uv run python scripts/modbus_server.py --input tests/fixtures/C4_registers_synthetic.json --port 5020

Then point the integration at 127.0.0.1:5020.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from pymodbus import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusServerContext,
    ModbusSparseDataBlock,
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def run_server(host: str, port: int, register_data: dict[str, list[int]]) -> None:
    """
    Serve ``register_data`` as holding registers.

    Keys are 1-based register numbers, matching ``scripts/modbus_dump.py`` output
    and the documentation. The datastore is keyed by wire address, so each run is
    stored at ``number - 1`` — the same offset the client applies on its side.
    Recent pymodbus (3.11+) looks addresses up directly; it no longer adds one.
    """
    block = ModbusSparseDataBlock({int(k) - 1: v for k, v in register_data.items()})
    context = ModbusServerContext(devices=ModbusDeviceContext(hr=block), single=True)

    identity = ModbusDeviceIdentification()
    identity.VendorName = "Komfovent"
    identity.ProductCode = "C4"
    identity.ModelName = "Simulator"

    _LOGGER.info("Serving on %s:%d", host, port)
    await StartAsyncTcpServer(context=context, identity=identity, address=(host, port))


def main() -> None:
    """Run the simulator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Listen address")
    parser.add_argument("--port", type=int, default=502, help="Listen port")
    parser.add_argument("--input", default="registers.json", help="Register dump JSON")
    args = parser.parse_args()

    try:
        with Path(args.input).open() as f:
            register_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _LOGGER.exception("Failed to load %s", args.input)
        sys.exit(1)

    asyncio.run(run_server(args.host, args.port, register_data))


if __name__ == "__main__":
    main()
