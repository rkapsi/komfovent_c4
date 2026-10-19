"""Config flow for the Komfovent C4 integration."""

from __future__ import annotations

import zoneinfo
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIME_ZONE
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_MODBUS_ADDRESS,
    DEFAULT_MODBUS_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MODBUS_ADDRESS_MAX,
    MODBUS_ADDRESS_MIN,
    OPT_UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

# The C4 keeps a wall clock with no notion of zones. This is the zone that
# clock is read and written in; it only differs from Home Assistant's when the
# unit is somewhere else.
TIME_ZONE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=sorted(zoneinfo.available_timezones()),
        mode=SelectSelectorMode.DROPDOWN,
        sort=True,
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS): vol.All(
            int, vol.Range(min=MODBUS_ADDRESS_MIN, max=MODBUS_ADDRESS_MAX)
        ),
        vol.Required(CONF_TIME_ZONE): TIME_ZONE_SELECTOR,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            OPT_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
        ): NumberSelector(
            NumberSelectorConfig(
                min=10,
                max=300,
                step=5,
                mode=NumberSelectorMode.SLIDER,
                unit_of_measurement="seconds",
            )
        ),
    }
)


class KomfoventC4ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Komfovent C4."""

    VERSION = 1

    def _already_configured(self, user_input: dict[str, Any]) -> bool:
        """
        Return whether an entry already points at this unit.

        A unit is a (host, port, Modbus address) triple rather than a host: one
        RS-485 bridge can front several C4s at different addresses, which is
        the whole point of asking for the address. Entries created before it
        was configurable store none and talk to ``DEFAULT_MODBUS_ADDRESS``, so
        compare against that rather than letting them match nothing.
        """
        candidate = (
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input[CONF_MODBUS_ADDRESS],
        )
        for entry in self._async_current_entries(include_ignore=False):
            unit = (
                entry.data[CONF_HOST],
                entry.data[CONF_PORT],
                entry.data.get(CONF_MODBUS_ADDRESS, DEFAULT_MODBUS_ADDRESS),
            )
            if unit == candidate:
                return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            if self._already_configured(user_input):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, {CONF_TIME_ZONE: self.hass.config.time_zone}
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry=reconfigure_entry,
                title=user_input[CONF_NAME],
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA,
                {CONF_TIME_ZONE: self.hass.config.time_zone, **reconfigure_entry.data},
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: ARG004
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Options flow handler for Komfovent C4."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
