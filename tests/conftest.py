"""Shared fixtures for the Komfovent C4 tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_socket
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.komfovent_c4.const import DOMAIN, SCHEDULE_COUNT
from custom_components.komfovent_c4.registers import Register


@pytest.fixture(autouse=True)
def _socket_per_marker(request: pytest.FixtureRequest):
    """
    Allow real sockets only for tests marked ``enable_socket``.

    pytest-homeassistant-custom-component disables sockets globally; the live
    tests need one to reach the simulator on localhost.
    """
    if request.node.get_closest_marker("enable_socket"):
        pytest_socket.enable_socket()
        yield
        pytest_socket.disable_socket(allow_unix_socket=True)
    else:
        yield


# A plausible running unit: powered on, winter, level 2, 20.0 C setpoint.
DEFAULT_DATA: dict[Register, int] = {
    Register.POWER: 1,
    Register.SEASON: 1,
    Register.TIME: 0x0805,
    Register.DAY_OF_WEEK: 1,
    Register.MONTH_DAY: 0x0509,
    Register.YEAR: 2026,
    Register.MODBUS_ADDRESS: 1,
    Register.ALARM_WARNINGS: 0,
    Register.ALARM_STOP_FLAGS: 0,
    Register.ALARM_STOP_CODE: 0,
    Register.RECUPERATOR_LEVEL: 80,
    Register.ELECTRIC_HEATER_LEVEL: 25,
    Register.WATER_HEATING_LEVEL: 0,
    Register.WATER_COOLING_LEVEL: 0,
    Register.VENTILATION_LEVEL_MANUAL: 2,
    Register.VENTILATION_LEVEL_CURRENT: 2,
    Register.OPERATION_MODE: 0,
    Register.INTAKE_INTENSITY_1: 30,
    Register.INTAKE_INTENSITY_2: 60,
    Register.INTAKE_INTENSITY_3: 90,
    Register.INTAKE_INTENSITY_4: 100,
    Register.EXHAUST_INTENSITY_1: 30,
    Register.EXHAUST_INTENSITY_2: 60,
    Register.EXHAUST_INTENSITY_3: 90,
    Register.EXHAUST_INTENSITY_4: 100,
    Register.OVR_ENABLE: 0,
    Register.OVR_TIME: 30,
    Register.OVR_TIME_CURRENT: 0,
    Register.AHU_FANS_STATUS: 1,
    Register.SUPPLY_FAN_LEVEL: 60,
    Register.EXHAUST_FAN_LEVEL: 60,
    Register.SUPPLY_AIR_TEMP: 195,
    Register.SETPOINT_TEMP: 200,
    Register.TEMP_CORRECTION: 0,
    Register.TEMP_CORRECTION_START: 0x0800,
    Register.TEMP_CORRECTION_STOP: 0x1600,
    Register.WATER_TEMP: 450,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the integration from custom_components/."""
    return


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Komfovent C4",
        data={
            CONF_NAME: "Komfovent C4",
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 502,
        },
    )


@pytest.fixture
def register_data() -> dict[Register, int]:
    """Return a mutable copy of the default register values."""
    return dict(DEFAULT_DATA)


@pytest.fixture
def mock_client(register_data):
    """Patch the Modbus client so no socket is opened."""
    with patch(
        "custom_components.komfovent_c4.coordinator.KomfoventC4Client"
    ) as mock_class:
        client = mock_class.return_value
        client.connect = AsyncMock(return_value=True)
        client.write = AsyncMock()
        client.close = lambda: None

        async def read_block(start, count):
            numbers = range(start.number, start.number + count)
            return {
                reg: value
                for reg, value in register_data.items()
                if reg.number in numbers
            }

        client.read_block = AsyncMock(side_effect=read_block)
        # The schedule block has no Register members; default to an empty one.
        client.read_words = AsyncMock(return_value=[0] * SCHEDULE_COUNT)
        yield client


@pytest.fixture
async def setup_integration(hass, config_entry, mock_client):
    """Set up the integration with a mocked device."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
