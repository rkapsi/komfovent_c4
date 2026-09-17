"""Switch platform for the Komfovent C4 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from .const import DOMAIN
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

SWITCHES: tuple[tuple[Register, SwitchEntityDescription], ...] = (
    (
        Register.POWER,
        SwitchEntityDescription(
            key="power",
            name="Power",
            device_class=SwitchDeviceClass.SWITCH,
        ),
    ),
    (
        Register.OVR_ENABLE,
        SwitchEntityDescription(
            key="boost",
            name="Boost",
            device_class=SwitchDeviceClass.SWITCH,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 switches."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KomfoventC4Switch(coordinator, description, register)
        for register, description in SWITCHES
    )


class KomfoventC4Switch(KomfoventC4Entity, SwitchEntity):
    """A switch backed by a single register."""

    @property
    def is_on(self) -> bool | None:
        """Return whether the register is non-zero."""
        value = self.raw_value
        return None if value is None else bool(value)

    async def async_turn_on(self, **_kwargs: object) -> None:
        """Turn the switch on."""
        await self.async_write(1)

    async def async_turn_off(self, **_kwargs: object) -> None:
        """Turn the switch off."""
        await self.async_write(0)
