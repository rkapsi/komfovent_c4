"""
Writes must not be undone by a stale read-back.

The C4 acknowledges a write before applying it; POWER takes about a second to
read back the new value. These tests simulate a unit that keeps reporting the
old value for a while and check the entity does not flip back in the meantime.
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.komfovent_c4.const import DOMAIN, WRITE_SETTLE_SECONDS
from custom_components.komfovent_c4.registers import Register

POWER = "switch.komfovent_c4_power"


async def _turn_off(hass):
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: POWER}, blocking=True
    )


async def _advance(hass, seconds: float):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_switch_shows_new_state_before_the_unit_does(
    hass, setup_integration, mock_client, register_data
):
    """The unit still reports ON after the write; the switch must show OFF."""
    assert hass.states.get(POWER).state == STATE_ON

    await _turn_off(hass)

    mock_client.write.assert_awaited_once_with(Register.POWER, 0)
    assert register_data[Register.POWER] == 1  # unit has not applied it yet
    assert hass.states.get(POWER).state == STATE_OFF


async def test_settle_refresh_reads_the_applied_value(
    hass, setup_integration, mock_client, register_data
):
    mock_client.read_block.reset_mock()
    await _turn_off(hass)
    assert not mock_client.read_block.await_count, "must not read straight back"

    register_data[Register.POWER] = 0  # the unit applies it during the window
    await _advance(hass, WRITE_SETTLE_SECONDS + 0.1)

    assert mock_client.read_block.await_count == 3
    assert hass.states.get(POWER).state == STATE_OFF


async def test_poll_during_settle_keeps_optimistic_value(
    hass, setup_integration, mock_client, register_data
):
    """A scheduled poll inside the window must not read the stale register."""
    await _turn_off(hass)
    mock_client.read_block.reset_mock()

    coordinator = hass.data[DOMAIN][setup_integration.entry_id]
    await coordinator.async_refresh()

    assert not mock_client.read_block.await_count
    assert hass.states.get(POWER).state == STATE_OFF


async def test_unit_that_ignores_the_write_wins_after_settle(
    hass, setup_integration, mock_client, register_data
):
    """Optimism ends at the settle refresh: the real register value is shown."""
    await _turn_off(hass)
    await _advance(hass, WRITE_SETTLE_SECONDS + 0.1)

    assert hass.states.get(POWER).state == STATE_ON


async def test_consecutive_writes_share_one_settle_refresh(
    hass, setup_integration, mock_client, register_data
):
    """The sync-clock button writes four registers; that is one refresh, not four."""
    mock_client.read_block.reset_mock()
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.komfovent_c4_sync_clock"},
        blocking=True,
    )
    assert mock_client.write.await_count == 4

    await _advance(hass, WRITE_SETTLE_SECONDS + 0.1)
    assert mock_client.read_block.await_count == 3


async def test_unload_cancels_pending_settle(hass, setup_integration, mock_client):
    await _turn_off(hass)
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    mock_client.read_block.reset_mock()
    await _advance(hass, WRITE_SETTLE_SECONDS + 0.1)
    assert not mock_client.read_block.await_count
