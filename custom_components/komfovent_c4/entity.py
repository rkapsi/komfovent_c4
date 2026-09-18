"""Shared entity base for the Komfovent C4 integration."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription

    from .coordinator import KomfoventC4Coordinator
    from .registers import Register


def build_device_info(coordinator: KomfoventC4Coordinator) -> DeviceInfo:
    """Build the device registry entry shared by every entity."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=coordinator.config_entry.title,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
    )


# Entities that only carry information when a water coil is fitted; keyed by
# description key so each platform can look its own up.
WATER_COIL_KEYS: frozenset[str] = frozenset(
    {
        "water_temperature",
        "water_heating_level",
        "water_cooling_level",
        "stop_water_temp_low",
    }
)


def for_hardware[D: EntityDescription](
    coordinator: KomfoventC4Coordinator, description: D
) -> D:
    """Return the description, disabled by default if its hardware is absent."""
    if description.key in WATER_COIL_KEYS and not coordinator.water_coil_fitted:
        return dataclasses.replace(description, entity_registry_enabled_default=False)
    return description


class KomfoventC4Entity(CoordinatorEntity["KomfoventC4Coordinator"]):
    """Base entity wired to a single register."""

    _attr_has_entity_name = True
    coordinator: KomfoventC4Coordinator

    def __init__(
        self,
        coordinator: KomfoventC4Coordinator,
        entity_description: EntityDescription,
        register: Register | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.register = register
        self.entity_description = for_hardware(coordinator, entity_description)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_translation_key = entity_description.key
        self._attr_device_info = build_device_info(coordinator)

    @property
    def raw_value(self) -> int | None:
        """Return the cached raw value of this entity's register."""
        if not self.coordinator.data or self.register is None:
            return None
        return self.coordinator.data.get(self.register)

    async def async_write(self, value: int) -> None:
        """Write to this entity's register and refresh."""
        if self.register is None:
            msg = f"{self.entity_id} has no register to write"
            raise ValueError(msg)
        await self.coordinator.async_write(self.register, value)
