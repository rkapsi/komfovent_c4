"""Config and options flow tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIME_ZONE
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.komfovent_c4.const import (
    CONF_MODBUS_ADDRESS,
    DOMAIN,
    OPT_UPDATE_INTERVAL,
)

USER_INPUT = {
    CONF_NAME: "Basement AHU",
    CONF_HOST: "192.0.2.20",
    CONF_PORT: 502,
    CONF_MODBUS_ADDRESS: 20,
    CONF_TIME_ZONE: "Europe/Tallinn",
}


async def test_user_flow_creates_entry(hass, mock_client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # The form suggests HA's own zone (US/Pacific in the test harness).
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_TIME_ZONE] == hass.config.time_zone

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Basement AHU"
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize("address", [0, 255])
async def test_user_flow_rejects_out_of_range_modbus_address(hass, address):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**USER_INPUT, CONF_MODBUS_ADDRESS: address}
        )


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({CONF_MODBUS_ADDRESS: 254}, 254),
        ({}, 1),  # entries created before the address was configurable
    ],
)
async def test_client_uses_entry_modbus_address(
    hass, config_entry, mock_client, data, expected
):
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **data}
    )

    with patch(
        "custom_components.komfovent_c4.coordinator.KomfoventC4Client",
        return_value=mock_client,
    ) as client_class:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert client_class.call_args.kwargs["device_id"] == expected


async def test_user_flow_rejects_duplicate_host(hass, config_entry, mock_client):
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**USER_INPUT, CONF_HOST: config_entry.data[CONF_HOST]},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_updates_entry(hass, setup_integration, mock_client):
    result = await setup_integration.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**USER_INPUT, CONF_HOST: "192.0.2.30", CONF_MODBUS_ADDRESS: 254},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert setup_integration.data[CONF_HOST] == "192.0.2.30"
    assert setup_integration.data[CONF_MODBUS_ADDRESS] == 254
    assert setup_integration.title == "Basement AHU"


async def test_options_flow_sets_update_interval(hass, setup_integration, mock_client):
    result = await hass.config_entries.options.async_init(setup_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={OPT_UPDATE_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_integration.options[OPT_UPDATE_INTERVAL] == 60

    coordinator = hass.data[DOMAIN][setup_integration.entry_id]
    assert coordinator.update_interval.total_seconds() == 60
