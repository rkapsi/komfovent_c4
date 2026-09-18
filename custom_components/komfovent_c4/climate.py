"""Climate platform for the Komfovent C4 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    DOMAIN,
    SETPOINT_MAX_TEMP,
    SETPOINT_MIN_TEMP,
    SETPOINT_STEP_TEMP,
    TEMP_NO_SENSOR,
    VentilationLevel,
)
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

_LOGGER = logging.getLogger(__name__)

DESCRIPTION = ClimateEntityDescription(key="climate", name=None)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 climate entity."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KomfoventC4Climate(coordinator, DESCRIPTION)])


class KomfoventC4Climate(KomfoventC4Entity, ClimateEntity):
    """The air handling unit as a single climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = SETPOINT_STEP_TEMP
    _attr_min_temp = SETPOINT_MIN_TEMP
    _attr_max_temp = SETPOINT_MAX_TEMP
    # HA declares these as instance attributes, so ClassVar would break ty.
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]  # noqa: RUF012
    _attr_fan_modes = [level.name.lower() for level in VentilationLevel]  # noqa: RUF012
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def _value(self, register: Register) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(register)

    @property
    def current_temperature(self) -> float | None:
        """Return the supply air temperature."""
        temp = self._value(Register.SUPPLY_AIR_TEMP)
        if temp is None or temp == TEMP_NO_SENSOR:
            return None
        return temp / 10

    @property
    def target_temperature(self) -> float | None:
        """Return the supply air setpoint."""
        temp = self._value(Register.SETPOINT_TEMP)
        return None if temp is None else temp / 10

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return whether the unit is running."""
        power = self._value(Register.POWER)
        if power is None:
            return None
        return HVACMode.HEAT_COOL if power else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return what the unit is currently doing."""
        power = self._value(Register.POWER)
        if power is None:
            return None
        if not power:
            return HVACAction.OFF
        if self._value(Register.WATER_COOLING_LEVEL):
            return HVACAction.COOLING
        if self._value(Register.ELECTRIC_HEATER_LEVEL) or self._value(
            Register.WATER_HEATING_LEVEL
        ):
            return HVACAction.HEATING
        if self._value(Register.AHU_FANS_STATUS):
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        """
        Return the selected ventilation level.

        This reports the manual level (1100) rather than the current level
        (1101), because 1101 also reports 0 (stopped) and 4 (boost), which are
        not selectable options.
        """
        try:
            return VentilationLevel(
                self._value(Register.VENTILATION_LEVEL_MANUAL)
            ).name.lower()
        except ValueError:
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the supply air setpoint."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        if not SETPOINT_MIN_TEMP <= temp <= SETPOINT_MAX_TEMP:
            _LOGGER.warning(
                "Temperature %.1f C out of bounds (%.1f-%.1f C)",
                temp,
                SETPOINT_MIN_TEMP,
                SETPOINT_MAX_TEMP,
            )
            return

        await self.coordinator.client.write(Register.SETPOINT_TEMP, int(temp * 10))
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the manual ventilation level."""
        try:
            level = VentilationLevel[fan_mode.upper()]
        except KeyError:
            _LOGGER.warning("Invalid ventilation level: %s", fan_mode)
            return

        await self.coordinator.client.write(
            Register.VENTILATION_LEVEL_MANUAL, level.value
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop the unit."""
        await self.coordinator.client.write(
            Register.POWER, 0 if hvac_mode == HVACMode.OFF else 1
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Start the unit."""
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        """Stop the unit."""
        await self.async_set_hvac_mode(HVACMode.OFF)
