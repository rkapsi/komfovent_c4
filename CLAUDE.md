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

`tests/test_registers.py` needs no Home Assistant runtime. The live tests in
`tests/test_live_modbus.py` need `--socket-enabled` and run against
`scripts/modbus_server.py`.

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
