"""
Tests for the C4 register map itself.

These guard the transcription in ``registers.py`` against the PDF, and against
the class of mistake where a typo silently turns one member into an alias of
another instead of raising.
"""

from __future__ import annotations

import pytest

from custom_components.komfovent_c4.registers import (
    BY_NUMBER,
    POLL_BLOCKS,
    Access,
    DataType,
    Register,
)


def test_no_aliased_members():
    """Every member must be distinct; a duplicate number would silently alias."""
    numbers = [reg.number for reg in Register]
    assert len(numbers) == len(set(numbers))
    assert len(list(Register)) == len(Register.__members__)


def test_address_is_one_below_documented_number():
    for reg in Register:
        assert reg.address == reg.number - 1


def test_by_number_covers_every_register():
    assert len(BY_NUMBER) == len(list(Register))
    for reg in Register:
        assert BY_NUMBER[reg.number] is reg


@pytest.mark.parametrize(
    ("register", "number"),
    [
        (Register.POWER, 1000),
        (Register.SEASON, 1001),
        (Register.ALARM_STOP_CODE, 1009),
        (Register.WATER_COOLING_LEVEL, 1013),
        (Register.VENTILATION_LEVEL_MANUAL, 1100),
        (Register.OPERATION_MODE, 1102),
        (Register.EXHAUST_FAN_LEVEL, 1116),
        (Register.SUPPLY_AIR_TEMP, 1200),
        (Register.SETPOINT_TEMP, 1201),
        # 1205, not 1203 -- 1203 is the correction start time.
        (Register.WATER_TEMP, 1205),
    ],
)
def test_documented_numbers(register, number):
    assert register.number == number


def test_water_temp_is_not_the_correction_start_time():
    assert Register.WATER_TEMP is not Register.TEMP_CORRECTION_START
    assert Register.WATER_TEMP.number != Register.TEMP_CORRECTION_START.number


def test_alarm_registers_are_bitfields():
    """Coercing these to 0/1 would destroy the individual alarm bits."""
    assert Register.ALARM_WARNINGS.datatype == DataType.BITFIELD
    assert Register.ALARM_STOP_FLAGS.datatype == DataType.BITFIELD


def test_read_only_registers():
    for reg in (
        Register.VENTILATION_LEVEL_CURRENT,
        Register.SUPPLY_AIR_TEMP,
        Register.WATER_TEMP,
        Register.SUPPLY_FAN_LEVEL,
        Register.ALARM_STOP_CODE,
    ):
        assert reg.access == Access.READ_ONLY


def test_poll_blocks_are_contiguous_and_complete():
    """Every register must be covered by exactly one polled block."""
    covered: list[int] = []
    for start, count in POLL_BLOCKS:
        covered.extend(range(start.number, start.number + count))

    assert len(covered) == len(set(covered))
    assert {reg.number for reg in Register} == set(covered)


def test_poll_blocks_have_no_gaps():
    """A gap would mean wasting a word on an undocumented register."""
    for start, count in POLL_BLOCKS:
        for number in range(start.number, start.number + count):
            assert number in BY_NUMBER


def test_str_includes_number():
    assert str(Register.POWER) == "POWER(1000)"
