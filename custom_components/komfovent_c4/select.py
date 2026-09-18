"""Select platform for the Komfovent C4 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, OperationMode, Season, VentilationLevel
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from enum import IntEnum

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

_LOGGER = logging.getLogger(__name__)

SELECTS: tuple[tuple[Register, type[IntEnum], SelectEntityDescription], ...] = (
    (
        Register.VENTILATION_LEVEL_MANUAL,
        VentilationLevel,
        SelectEntityDescription(
            key="ventilation_level",
            name="Ventilation level",
            options=[level.name.lower() for level in VentilationLevel],
        ),
    ),
    (
        Register.OPERATION_MODE,
        OperationMode,
        SelectEntityDescription(
            key="operation_mode",
            name="Operation mode",
            options=[mode.name.lower() for mode in OperationMode],
        ),
    ),
    (
        Register.SEASON,
        Season,
        SelectEntityDescription(
            key="season",
            name="Season",
            options=[season.name.lower() for season in Season],
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 selects."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        (
            OperationModeSelect
            if register is Register.OPERATION_MODE
            else KomfoventC4Select
        )(coordinator, description, register, enum_class)
        for register, enum_class, description in SELECTS
    )


class KomfoventC4Select(KomfoventC4Entity, SelectEntity):
    """A select mapping a register to an enum."""

    def __init__(
        self,
        coordinator: KomfoventC4Coordinator,
        entity_description: SelectEntityDescription,
        register: Register,
        enum_class: type[IntEnum],
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, entity_description, register)
        self.enum_class = enum_class

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = self.raw_value
        if value is None:
            return None
        try:
            return self.enum_class(value).name.lower()
        except ValueError:
            return None

    async def async_select_option(self, option: str) -> None:
        """Write the selected option to the register."""
        try:
            member = self.enum_class[option.upper()]
        except KeyError:
            _LOGGER.warning("Invalid option for %s: %s", self.entity_id, option)
            return
        await self.async_write(member.value)


class OperationModeSelect(KomfoventC4Select):
    """
    Register 1102: manual level, or the unit's own weekly schedule.

    Scheduling is expected to live in Home Assistant (see the README), so the
    unit's schedule is normally empty — and under AUTO an empty schedule means
    the unit stays off. Refuse that switch rather than let it look like a fault.
    """

    async def async_select_option(self, option: str) -> None:
        """Write the mode, refusing AUTO while the unit's schedule is empty."""
        if (
            option == OperationMode.AUTO.name.lower()
            and not await self.coordinator.async_schedule_runs_anything()
        ):
            # The dropdown shows the refused option until a state event
            # arrives, and with the state unchanged none would until the next
            # poll. Force one so it snaps back at once.
            self._attr_force_update = True
            try:
                self.async_write_ha_state()
            finally:
                self._attr_force_update = False
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="schedule_empty"
            )
        await super().async_select_option(option)
