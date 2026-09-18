"""Entity-level tests against a mocked C4."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_TEMPERATURE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_TIME_ZONE, STATE_OFF, STATE_ON
from homeassistant.exceptions import ServiceValidationError
from pymodbus import ModbusException

from custom_components.komfovent_c4.const import DOMAIN, SCHEDULE_COUNT, SCHEDULE_SLOTS
from custom_components.komfovent_c4.registers import Register

CLIMATE = "climate.komfovent_c4"


async def test_setup_creates_entities(hass, setup_integration):
    """The integration should come up and register its platforms."""
    assert hass.states.get(CLIMATE) is not None
    assert hass.states.get("sensor.komfovent_c4_supply_air_temperature") is not None
    assert hass.states.get("switch.komfovent_c4_power") is not None
    assert hass.states.get("select.komfovent_c4_season") is not None


async def test_climate_scales_temperatures(hass, setup_integration):
    """Temperature registers hold tenths of a degree."""
    state = hass.states.get(CLIMATE)
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == pytest.approx(19.5)
    assert state.attributes[ATTR_TEMPERATURE] == pytest.approx(20.0)
    assert state.attributes[ATTR_FAN_MODE] == "level_2"


async def test_climate_reports_heating(hass, setup_integration):
    """The electric heater running means the unit is heating."""
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING


async def test_climate_reports_off_when_powered_down(
    hass, config_entry, mock_client, register_data
):
    register_data[Register.POWER] = 0
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF


async def test_set_temperature_writes_scaled_value(
    hass, setup_integration, mock_client
):
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    # 21.5 is not representable; the nearest even tenth wins.
    mock_client.write.assert_awaited_with(Register.SETPOINT_TEMP, 216)


async def test_set_temperature_rounds_to_even_tenths(
    hass, setup_integration, mock_client
):
    """The C4 keeps the setpoint in 0.2 C steps; 21.3 must not be sent as 213."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 21.3},
        blocking=True,
    )
    mock_client.write.assert_awaited_with(Register.SETPOINT_TEMP, 212)


async def test_set_temperature_out_of_bounds_is_ignored(
    hass, setup_integration, mock_client
):
    """The C4 setpoint tops out at 30.0 C."""
    mock_client.write.reset_mock()

    with pytest.raises(Exception, match=r".*"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 45.0},
            blocking=True,
        )

    mock_client.write.assert_not_awaited()


async def test_set_fan_mode_writes_manual_level(hass, setup_integration, mock_client):
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_FAN_MODE: "level_3"},
        blocking=True,
    )

    mock_client.write.assert_awaited_with(Register.VENTILATION_LEVEL_MANUAL, 3)


async def test_switch_turn_on_off(hass, setup_integration, mock_client):
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: "switch.komfovent_c4_power"},
        blocking=True,
    )
    mock_client.write.assert_awaited_with(Register.POWER, 0)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: "switch.komfovent_c4_power"},
        blocking=True,
    )
    mock_client.write.assert_awaited_with(Register.POWER, 1)


async def test_select_writes_enum_value(hass, setup_integration, mock_client):
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.komfovent_c4_season", "option": "summer"},
        blocking=True,
    )

    mock_client.write.assert_awaited_with(Register.SEASON, 0)


async def test_number_writes_scaled_correction(hass, setup_integration, mock_client):
    await hass.services.async_call(
        "number",
        "set_value",
        {
            ATTR_ENTITY_ID: "number.komfovent_c4_temperature_correction",
            "value": -2.5,
        },
        blocking=True,
    )

    mock_client.write.assert_awaited_with(Register.TEMP_CORRECTION, -25)


async def test_alarm_bits_become_separate_binary_sensors(
    hass, config_entry, mock_client, register_data
):
    """Bit 14 is 'service required', bit 11 is 'rotor stopped'."""
    register_data[Register.ALARM_WARNINGS] = (1 << 14) | (1 << 11)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.komfovent_c4_service_required").state == STATE_ON
    )
    assert hass.states.get("binary_sensor.komfovent_c4_rotor_stopped").state == STATE_ON
    assert hass.states.get("binary_sensor.komfovent_c4_heater_off").state == STATE_OFF


async def test_stop_code_is_decoded(hass, config_entry, mock_client, register_data):
    register_data[Register.ALARM_STOP_CODE] = 28
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.komfovent_c4_stop_reason").state == "frost_possibility"
    )


async def test_water_temperature_reads_register_1205(hass, setup_integration):
    """Guards the transcription bug where water temp pointed at 1203."""
    assert hass.states.get("sensor.komfovent_c4_water_temperature").state == "45.0"


async def test_missing_sensor_reads_unknown(
    hass, config_entry, mock_client, register_data
):
    """A unit without a water coil reports 0x7FFF on 1205, not a temperature."""
    register_data[Register.WATER_TEMP] = 0x7FFF
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.komfovent_c4_water_temperature").state == "unknown"


async def test_clock_sensor_assembles_local_datetime(hass, setup_integration):
    """8:05 on 9 May 2026 in the fixture, shown as the panel would show it."""
    state = hass.states.get("sensor.komfovent_c4_clock")
    assert state.state == "2026-05-09 08:05"
    # Test HA runs in US/Pacific; the controller clock is taken as local time.
    assert state.attributes["timestamp"] == "2026-05-09T08:05:00-07:00"


async def test_clock_uses_configured_zone(hass, config_entry, mock_client):
    """A unit in another zone: its wall clock is read in that zone, not HA's."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TIME_ZONE: "Europe/Tallinn"}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.komfovent_c4_clock")
    assert state.state == "2026-05-09 08:05"
    assert state.attributes["timestamp"] == "2026-05-09T08:05:00+03:00"


async def test_sync_clock_writes_configured_zone(
    hass, config_entry, mock_client, freezer
):
    """08:05 UTC is 11:05 in Tallinn; that is what the controller must get."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_TIME_ZONE: "Europe/Tallinn"}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to("2026-05-09 08:05:00+00:00")
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.komfovent_c4_sync_clock"},
        blocking=True,
    )

    calls = [c.args for c in mock_client.write.await_args_list]
    assert (Register.TIME, 0x0B05) in calls


async def test_clock_sensor_unknown_on_garbage(
    hass, config_entry, mock_client, register_data
):
    register_data[Register.MONTH_DAY] = 0x0D20  # month 13
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.komfovent_c4_clock").state == "unknown"


async def test_unload(hass, setup_integration):
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).state == "unavailable"


async def test_climate_hvac_action_branches(
    hass, config_entry, mock_client, register_data
):
    """Cooling beats heating beats fan beats idle."""
    register_data[Register.ELECTRIC_HEATER_LEVEL] = 0
    register_data[Register.WATER_COOLING_LEVEL] = 40
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    register_data[Register.WATER_COOLING_LEVEL] = 0
    await coordinator.async_refresh()
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.FAN

    register_data[Register.AHU_FANS_STATUS] = 0
    await coordinator.async_refresh()
    assert hass.states.get(CLIMATE).attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_climate_turn_on_off(hass, setup_integration, mock_client):
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: CLIMATE}, blocking=True
    )
    mock_client.write.assert_awaited_with(Register.POWER, 0)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CLIMATE}, blocking=True
    )
    mock_client.write.assert_awaited_with(Register.POWER, 1)


async def test_climate_unknown_fan_level_reads_none(
    hass, config_entry, mock_client, register_data
):
    """1100 outside 1..3 is not a selectable level."""
    register_data[Register.VENTILATION_LEVEL_MANUAL] = 4
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE).attributes[ATTR_FAN_MODE] is None


async def test_select_reflects_register(hass, setup_integration):
    assert hass.states.get("select.komfovent_c4_season").state == "winter"
    assert hass.states.get("select.komfovent_c4_operation_mode").state == "manual"
    assert hass.states.get("select.komfovent_c4_ventilation_level").state == "level_2"


OPERATION_MODE = "select.komfovent_c4_operation_mode"


async def _select(hass, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": option},
        blocking=True,
    )


async def test_operation_mode_refuses_auto_with_empty_schedule(
    hass, setup_integration, mock_client
):
    """The unit stays off under AUTO with nothing scheduled; do not let it."""
    mock_client.write.reset_mock()
    with pytest.raises(ServiceValidationError) as excinfo:
        await _select(hass, OPERATION_MODE, "auto")

    assert excinfo.value.translation_key == "schedule_empty"
    mock_client.read_words.assert_awaited_once_with(1300, SCHEDULE_COUNT)
    mock_client.write.assert_not_awaited()
    assert hass.states.get(OPERATION_MODE).state == "manual"


@pytest.mark.parametrize(
    "slot",
    [(0x0600, 0x0600, 2), (0x0800, 0x0600, 2), (0x0600, 0x0800, 0)],
    ids=["zero-length", "ends-before-start", "level-0"],
)
async def test_operation_mode_ignores_slots_that_run_nothing(
    hass, setup_integration, mock_client, slot
):
    words = [0] * SCHEDULE_COUNT
    words[0], words[1], words[2 * SCHEDULE_SLOTS] = slot
    mock_client.read_words.return_value = words

    with pytest.raises(ServiceValidationError):
        await _select(hass, OPERATION_MODE, "auto")


async def test_operation_mode_switches_to_auto_with_a_schedule(
    hass, setup_integration, mock_client
):
    words = [0] * SCHEDULE_COUNT
    # Sunday's third slot: 22:00-24:00 at level 1.
    words[40], words[41], words[SCHEDULE_COUNT - 1] = 0x1600, 0x1800, 1
    mock_client.read_words.return_value = words
    mock_client.write.reset_mock()

    await _select(hass, OPERATION_MODE, "auto")

    mock_client.write.assert_awaited_once_with(Register.OPERATION_MODE, 1)
    assert hass.states.get(OPERATION_MODE).state == "auto"


async def test_operation_mode_manual_does_not_read_the_schedule(
    hass, setup_integration, mock_client, register_data
):
    register_data[Register.OPERATION_MODE] = 1
    await hass.config_entries.async_reload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(OPERATION_MODE).state == "auto"
    mock_client.write.reset_mock()

    await _select(hass, OPERATION_MODE, "manual")

    mock_client.read_words.assert_not_awaited()
    mock_client.write.assert_awaited_once_with(Register.OPERATION_MODE, 0)


async def test_select_rejects_unknown_option(hass, setup_integration, mock_client):
    mock_client.write.reset_mock()
    with pytest.raises(Exception, match=r".*"):
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: "select.komfovent_c4_season", "option": "monsoon"},
            blocking=True,
        )
    mock_client.write.assert_not_awaited()


async def test_sync_clock_button_packs_bytes(
    hass, setup_integration, mock_client, freezer
):
    """8:05 local on Saturday 9 May 2026 => 0x0805, 0x0509, 6, 2026."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-05-09 08:05:00+00:00")
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.komfovent_c4_sync_clock"},
        blocking=True,
    )

    calls = [c.args for c in mock_client.write.await_args_list]
    assert (Register.TIME, 0x0805) in calls
    assert (Register.MONTH_DAY, 0x0509) in calls
    assert (Register.DAY_OF_WEEK, 6) in calls
    assert (Register.YEAR, 2026) in calls


async def test_coordinator_marks_entities_unavailable_on_error(
    hass, setup_integration, mock_client
):
    mock_client.read_block.side_effect = ModbusException("gateway gone")
    coordinator = hass.data[DOMAIN][setup_integration.entry_id]
    await coordinator.async_refresh()

    assert hass.states.get(CLIMATE).state == "unavailable"
