"""The Komfovent C4 integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, OPT_UPDATE_INTERVAL
from .coordinator import KomfoventC4Coordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Komfovent C4 from a config entry."""
    update_interval = entry.options.get(OPT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    coordinator = KomfoventC4Coordinator(
        hass=hass,
        config_entry=entry,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.connect()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]
    update_interval = entry.options.get(OPT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator.update_interval = timedelta(seconds=update_interval)
    _LOGGER.debug("Update interval changed to %s seconds", update_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: KomfoventC4Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.client.close()
    return unload_ok
