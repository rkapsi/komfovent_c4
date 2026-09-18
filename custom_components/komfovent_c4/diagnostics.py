"""Diagnostics support for the Komfovent C4."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_HOST, CONF_PORT
from pymodbus import ModbusException

from .const import DOMAIN
from .dump import dump_registers

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import KomfoventC4Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]

    try:
        registers = await dump_registers(entry.data[CONF_HOST], entry.data[CONF_PORT])
    except (ConnectionError, ModbusException):
        _LOGGER.exception("Failed to dump registers")
        registers = {}

    return {
        "config_entry": entry.as_dict(),
        "registers": registers,
        "coordinator_data": {
            str(register): value for register, value in (coordinator.data or {}).items()
        },
    }
