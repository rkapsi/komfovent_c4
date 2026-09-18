# CLAUDE.md

Home Assistant custom integration for Komfovent DOMEKT units with the **C4**
controller, over Modbus TCP. C4 only — the C6/C6M/C8 controllers are covered by
the separate lnagel/hass-komfovent project and are deliberately out of scope.

## Source of truth

`docs/MODBUS_C4.pdf` is the only primary source. `docs/MODBUS_C4.md` is its
transcription and `custom_components/komfovent_c4/registers.py` is that
transcription as code. When any of the three disagree, the PDF wins; when
entities or registers change, update both the `.md` and `registers.py`.

Register numbers in the PDF are 1-based. The Modbus address on the wire is
`number - 1`. This is confirmed against real hardware — do not change it.

## Checks

```bash
uv sync --dev
uv run pytest
uv run ruff format .
uv run ruff check . --fix
uv run ty check
```

Without `uv`: `python3 -m venv .venv && .venv/bin/pip install
pytest-homeassistant-custom-component ruff ty`, then `.venv/bin/python -m pytest`.

`tests/test_registers.py` needs no Home Assistant runtime. The live tests in
`tests/test_live_modbus.py` are marked `enable_socket` and run against
`scripts/modbus_server.py` serving `tests/fixtures/C4_registers_mine.json`
(a real dump) and `C4_registers_synthetic.json`. `scripts/modbus_dump.py` must
stay runnable with only pymodbus installed — that is why `dump.py` imports
nothing from Home Assistant or the rest of the package.

Temperature registers read `0x7FFF` when the sensor is not fitted
(`TEMP_NO_SENSOR`); treat that as unknown, never as a temperature.

All writes go through `KomfoventC4Coordinator.async_write`, never
`client.write` from an entity. The controller acks writes before applying them
(POWER takes ~1 s to read back), so `async_write` updates the cache
optimistically and defers the read by `WRITE_SETTLE_SECONDS`; reading straight
back flips the entity to the stale value. Measured behaviour is recorded under
"Observed on hardware" in `docs/MODBUS_C4.md` — add to it when you learn more.

The setpoint (1201) only holds even tenths of a degree; round before writing.

The controller's clock (1002-1005) is, by decision, in Home Assistant's local
time zone: the C4 has no zone concept, the sync button writes HA local time,
and the clock sensor reads it back the same way. Do not add zone handling.

## Shape

- One `Register` enum carrying `(number, datatype, access)`. All C4 registers
  are single 16-bit words; there is no 32-bit handling anywhere and none is
  needed.
- The coordinator polls exactly `POLL_BLOCKS` — three block reads per cycle.
  Never read registers one at a time in the poll loop; the unit is often
  behind a 19200-baud serial bridge.
- `entity.py` holds the one base class every platform subclasses. Platforms
  are flat tables of `(Register, EntityDescription)`; add entities there.
- Alarm registers 1007/1008 are bitfields. Never coerce them to 0/1.
- The weekly schedule (1300-1362) is documented, dumped by diagnostics, but
  not polled and has no entities. That is a decision, not an omission.
