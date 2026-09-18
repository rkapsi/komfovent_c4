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

The register map and the addressing convention (the integration sends
`documented number − 1` as the Modbus address) are confirmed against a real
C4 unit; `tests/fixtures/C4_registers_mine.json` is a dump from it and the
test suite runs against that dump. The entities have not yet been exercised
in a live Home Assistant against the hardware.

## Installation

### HACS

This is not in the HACS default store; add it as a custom repository:

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Repository: `https://github.com/rkapsi/komfovent_c4`, type: **Integration**.
3. Find **Komfovent C4** in HACS, download it and restart Home Assistant.
4. Add the integration from **Settings → Devices & services → Add integration**.

HACS offers the latest GitHub release; pushing a `v*` tag publishes one (see
`.github/workflows/release.yml`). With no releases it offers the default branch
instead, and **Redownload** pulls whatever is on it — handy while developing.

### Manual

Copy `custom_components/komfovent_c4/` into your Home Assistant
`config/custom_components/` directory and restart, then add the integration
from **Settings → Devices & services**.

You will need the IP address of the unit — or of the Komfovent "Ping" gateway
in front of it — and the Modbus TCP port, which the documentation gives as 502.

The form also asks for the time zone the controller's clock is kept in. It
defaults to Home Assistant's own zone, which is right unless the unit is
somewhere else; the clock sensor and the sync-clock button both use it.

## Entities

| Platform | Entities |
| --- | --- |
| Climate | The unit itself: supply air temperature, setpoint (0–30 °C), on/off, and ventilation level as the fan mode |
| Sensor | Supply air and water temperature, recuperator / electric heater / water heating / water cooling levels, supply and exhaust fan levels, current ventilation level, boost time remaining, stop reason, the controller's clock |
| Binary sensor | Fans running, plus one entity per documented warning and stop flag |
| Switch | Power, boost |
| Select | Ventilation level, operation mode (manual / weekly schedule), season |
| Number | Intake and exhaust intensity for levels 1–3 and for boost (level 4), boost duration, temperature correction |
| Button | Sync clock — writes Home Assistant's local time to the controller |

## Scheduling

The C4 has its own weekly schedule (three time slots per day, registers
1300–1362) that runs when the operation mode is set to *Unit's weekly
schedule*. This integration deliberately does not edit it: Home Assistant's
built-in **Schedule** helper is a far better editor, and it isn't limited to
three slots a day.

Keep the operation mode on *Manual* and let Home Assistant drive the level:

1. Settings → Devices & services → Helpers → Create helper → **Schedule**.
   Paint the weekly grid; give each block a data field `level` with the value
   `level_1`, `level_2` or `level_3`. Leave gaps where the unit should run at
   its base level.
2. One automation applies it:

   ```yaml
   alias: Ventilation schedule
   triggers:
     - trigger: state
       entity_id: schedule.ventilation
   actions:
     - action: select.select_option
       target:
         entity_id: select.komfovent_c4_ventilation_level
       data:
         option: >-
           {{ state_attr('schedule.ventilation', 'level') or 'level_1' }}
   ```

   The `or 'level_1'` is the level used outside every block. Replace the
   select with `switch.komfovent_c4_power` if you would rather switch the unit
   off outright.

Because the unit's own schedule is normally empty in this setup, and an empty
schedule under *Weekly schedule* keeps the unit **off**, the operation
mode select refuses to switch to it while nothing is programmed on the unit.
The schedule registers are read only at that moment; they are never polled.

## Development

```bash
uv sync --dev

uv run pytest
uv run ruff format .
uv run ruff check . --fix
uv run ty check
```

Without `uv`, a plain virtualenv works the same way:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component ruff ty
.venv/bin/python -m pytest
```

`tests/test_registers.py` and `tests/test_modbus.py` check the register map
and the client in isolation; `tests/test_entities.py` and
`tests/test_config_flow.py` run the integration against a mocked client; and
`tests/test_live_modbus.py` runs the real client over a socket against
`scripts/modbus_server.py` serving both the synthetic and the real dump.

### Working without the hardware

Dump every documented register from the real unit once. This needs only
`pymodbus`, not a Home Assistant install, so it can run from any machine that
can reach the unit:

```bash
python3 scripts/modbus_dump.py --host <unit-ip> --output tests/fixtures/C4_registers_mine.json
```

Then serve that dump as a fake C4 and point the integration (or the live
tests) at it:

```bash
uv run python scripts/modbus_server.py --input tests/fixtures/C4_registers_mine.json --port 5020
uv run pytest tests/test_live_modbus.py -v
```

`tests/fixtures/C4_registers_synthetic.json` is a hand-written dump in the same
format for when no real one is available. The dump is also what Home Assistant's
**Download diagnostics** button produces for the device.

## Credits

The entity structure and Modbus handling started as a fork of
[lnagel/hass-komfovent](https://github.com/lnagel/hass-komfovent) by Lenno
Nagel, and this integration keeps its overall shape. Licensed under the same
terms — see [LICENSE](LICENSE).
