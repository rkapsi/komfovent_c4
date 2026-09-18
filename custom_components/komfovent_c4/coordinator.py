"""DataUpdateCoordinator for the Komfovent C4 integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from pymodbus.exceptions import ModbusException

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, WRITE_SETTLE_SECONDS
from .modbus import KomfoventC4Client
from .registers import POLL_BLOCKS, Register

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class KomfoventC4Coordinator(TimestampDataUpdateCoordinator[dict[Register, int]]):
    """Polls the three C4 register blocks and caches the result."""

    config_entry: ConfigEntry
    client: KomfoventC4Client

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        **kwargs: Any,
    ) -> None:
        """Initialize the coordinator."""
        kwargs.setdefault("name", DOMAIN)
        kwargs.setdefault("update_interval", timedelta(seconds=DEFAULT_UPDATE_INTERVAL))

        super().__init__(hass, _LOGGER, config_entry=config_entry, **kwargs)

        self.client = KomfoventC4Client(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
        )
        self._cancel_settle: Callable[[], None] | None = None

    async def connect(self) -> bool:
        """
        Connect to the device.

        The C4 exposes no firmware or model register, so there is nothing to
        probe here -- reaching the socket is the only available check that the
        configured host is really a C4.
        """
        if not await self.client.connect():
            msg = "Failed to connect to Komfovent C4 device"
            raise ConfigEntryNotReady(msg)
        return True

    async def async_write(self, register: Register, value: int) -> None:
        """
        Write a register and show the new value without waiting for the unit.

        The cached value is replaced immediately so entities reflect the
        change at once, then a refresh is scheduled for after the controller
        has had time to apply it (see ``WRITE_SETTLE_SECONDS``). Reading
        straight back would return the old value and flip the entity back.
        """
        await self.client.write(register, value)

        if self.data is not None:
            self.async_set_updated_data({**self.data, register: value})

        if self._cancel_settle is not None:
            self._cancel_settle()
        self._cancel_settle = async_call_later(
            self.hass, WRITE_SETTLE_SECONDS, self._async_settled
        )

    async def _async_settled(self, _now: datetime) -> None:
        self._cancel_settle = None
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        """Cancel any pending settle refresh, then shut down."""
        if self._cancel_settle is not None:
            self._cancel_settle()
            self._cancel_settle = None
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[Register, int]:
        """Fetch all polled registers."""
        if self._cancel_settle is not None and self.data is not None:
            # A write is still settling; keep the optimistic values rather than
            # read the stale ones. The settle refresh follows shortly.
            return self.data

        data: dict[Register, int] = {}
        try:
            for start, count in POLL_BLOCKS:
                data.update(await self.client.read_block(start, count))
        except (ConnectionError, ModbusException) as error:
            _LOGGER.warning("Error communicating with Komfovent C4: %s", error)
            raise UpdateFailed from error
        return data
