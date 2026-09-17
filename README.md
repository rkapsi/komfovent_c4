# Komfovent C4

A Home Assistant integration for Komfovent DOMEKT air handling units with the
**C4** controller, over Modbus TCP.

This is a separate integration from
[lnagel/hass-komfovent](https://github.com/lnagel/hass-komfovent), which covers
the newer C6, C6M and C8 controllers. The C4 is a 2013-era controller that
shares no registers, no discovery mechanism and almost no feature set with
those, so keeping it separate is simpler than branching on controller type
throughout a combined codebase. If you have a C6, C6M or C8, use that
integration instead.

## Status

Written against the register map in [`docs/MODBUS_C4.pdf`](docs/MODBUS_C4.pdf)
and documented in [`docs/MODBUS_C4.md`](docs/MODBUS_C4.md).

The register addressing convention (the integration sends
`documented number − 1` as the Modbus address) has been confirmed against a
real C4 unit. The entity set in this rewrite has not yet been run against
hardware.

## Installation

Copy `custom_components/komfovent_c4/` into your Home Assistant
`config/custom_components/` directory and restart, then add the integration
from **Settings → Devices & services**.

You will need the IP address of the unit — or of the Komfovent "Ping" gateway
in front of it — and the Modbus TCP port, which the documentation gives as 502.

## Entities

| Platform | Entities |
| --- | --- |
| Climate | The unit itself: supply air temperature, setpoint (0–30 °C), on/off, and ventilation level as the fan mode |
| Sensor | Supply air and water temperature, recuperator / electric heater / water heating / water cooling levels, supply and exhaust fan levels, current ventilation level, boost time remaining, stop reason |
| Binary sensor | Fans running, plus one entity per documented warning and stop flag |
| Switch | Power, boost |
| Select | Ventilation level, operation mode (manual/auto), season |
| Number | Intake and exhaust intensity for levels 1–4, boost duration, temperature correction |
| Button | Sync clock — writes Home Assistant's local time to the controller |

The weekly schedule (registers 1300–1362) is deliberately not implemented; see
the notes in `docs/MODBUS_C4.md`.

## Development

```bash
uv sync --dev

uv run pytest
uv run ruff format .
uv run ruff check . --fix
uv run ty check
```

`tests/test_registers.py` checks the register map transcription on its own and
needs no Home Assistant runtime; the rest of the suite runs against a mocked
Modbus client.

### Working without the hardware

Dump every documented register from the real unit once:

```bash
uv run python scripts/modbus_dump.py --host <unit-ip> --output tests/fixtures/C4_registers_mine.json
```

Then serve that dump as a fake C4 and point the integration (or the live
tests) at it:

```bash
uv run python scripts/modbus_server.py --input tests/fixtures/C4_registers_mine.json --port 5020
uv run pytest tests/test_live_modbus.py -v --socket-enabled
```

`tests/fixtures/C4_registers_synthetic.json` is a hand-written dump in the same
format for when no real one is available. The dump is also what Home Assistant's
**Download diagnostics** button produces for the device.

## Credits

The entity structure and Modbus handling started as a fork of
[lnagel/hass-komfovent](https://github.com/lnagel/hass-komfovent) by Lenno
Nagel, and this integration keeps its overall shape. Licensed under the same
terms — see [LICENSE](LICENSE).
