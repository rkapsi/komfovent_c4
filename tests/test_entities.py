"""Entity-level tests against a mocked C4."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON

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


async def test_set_temperature_writes_scaled_value(hass, setup_integration, mock_client):
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    mock_client.write.assert_awaited_with(Register.SETPOINT_TEMP, 215)


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

    assert hass.states.get("binary_sensor.komfovent_c4_service_required").state == STATE_ON
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


async def test_unload(hass, setup_integration):
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).state == "unavailable"
