"""Button platform for the Komfovent C4 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 buttons."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SyncClockButton(
                coordinator,
                ButtonEntityDescription(
                    key="sync_clock",
                    name="Sync clock",
                    entity_category=EntityCategory.CONFIG,
                ),
            )
        ]
    )


class SyncClockButton(KomfoventC4Entity, ButtonEntity):
    """
    Writes Home Assistant's local time to the controller.

    The C4 has no NTP support and its clock drifts, which matters because the
    weekly schedule runs off it.
    """

    async def async_press(self) -> None:
        """Write the current local date and time to the controller."""
        now = dt_util.now()

        # The documentation packs these as two bytes per register:
        # 8:05 => 0x0805 and 9 May => 0x0509.
        await self.coordinator.client.write(
            Register.TIME, (now.hour << 8) | now.minute
        )
        await self.coordinator.client.write(
            Register.MONTH_DAY, (now.month << 8) | now.day
        )
        # Day of the week is 1-Mon..7-Sun, matching isoweekday().
        await self.coordinator.client.write(Register.DAY_OF_WEEK, now.isoweekday())
        await self.coordinator.client.write(Register.YEAR, now.year)

        await self.coordinator.async_request_refresh()
