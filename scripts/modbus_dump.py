#!/usr/bin/env python3
"""
Dump every documented C4 register from a real unit to JSON.

Run this once against the hardware; the output feeds ``scripts/modbus_server.py``
so that everything else can be developed and tested without the unit.

Only pymodbus is required — Home Assistant does not need to be installed:

    python3 scripts/modbus_dump.py --host 192.168.1.50 --output tests/fixtures/C4_registers_mine.json
"""

import argparse
import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path

from pymodbus.exceptions import ModbusException

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)

_DUMP_MODULE = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "komfovent_c4"
    / "dump.py"
)


def _load_dump_registers():  # noqa: ANN202
    """
    Load ``dump_registers`` without importing the integration package.

    The package ``__init__`` pulls in Home Assistant; ``dump.py`` is kept free of
    both HA and relative imports precisely so it can be loaded on its own here.
    """
    spec = importlib.util.spec_from_file_location("komfovent_c4_dump", _DUMP_MODULE)
    if spec is None or spec.loader is None:
        msg = f"Cannot load {_DUMP_MODULE}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.dump_registers


def main() -> None:
    """Run the register dump."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Modbus TCP host")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port")
    parser.add_argument("--output", default="registers.json", help="Output JSON file")
    args = parser.parse_args()

    dump_registers = _load_dump_registers()

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
