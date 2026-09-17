#!/usr/bin/env python3
"""
Dump every documented C4 register from a real unit to JSON.

Run this once against the hardware; the output feeds ``scripts/modbus_server.py``
so that everything else can be developed and tested without the unit.

    uv run python scripts/modbus_dump.py --host 192.168.1.50 --output tests/fixtures/C4_registers_mine.json
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from pymodbus.exceptions import ModbusException

from custom_components.komfovent_c4.diagnostics import dump_registers

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Run the register dump."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Modbus TCP host")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port")
    parser.add_argument("--output", default="registers.json", help="Output JSON file")
    args = parser.parse_args()

    try:
        _LOGGER.info("Connecting to %s:%d", args.host, args.port)
        registers = asyncio.run(dump_registers(args.host, args.port))
    except (ConnectionError, ModbusException):
        _LOGGER.exception("Dump failed")
        sys.exit(1)

    with Path(args.output).open("w") as f:
        json.dump(registers, f, indent=2)
    _LOGGER.info("Wrote %d register runs to %s", len(registers), args.output)


if __name__ == "__main__":
    main()
