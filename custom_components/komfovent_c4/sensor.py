"""Sensor platform for the Komfovent C4 integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TEMP_NO_SENSOR, StopCode
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

_LOGGER = logging.getLogger(__name__)

TEMPERATURE_SENSORS: tuple[tuple[Register, SensorEntityDescription], ...] = (
    (
        Register.SUPPLY_AIR_TEMP,
        SensorEntityDescription(
            key="supply_air_temperature",
            name="Supply air temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=1,
        ),
    ),
    (
        Register.WATER_TEMP,
        SensorEntityDescription(
            key="water_temperature",
            name="Water temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=1,
        ),
    ),
    (
        Register.TEMP_CORRECTION,
        SensorEntityDescription(
            key="temperature_correction",
            name="Temperature correction",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=1,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
)

PERCENT_SENSORS: tuple[tuple[Register, SensorEntityDescription], ...] = (
    (
        Register.RECUPERATOR_LEVEL,
        SensorEntityDescription(
            key="recuperator_level",
            name="Recuperator level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        Register.ELECTRIC_HEATER_LEVEL,
        SensorEntityDescription(
            key="electric_heater_level",
            name="Electric heater level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        Register.WATER_HEATING_LEVEL,
        SensorEntityDescription(
            key="water_heating_level",
            name="Water heating level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        Register.WATER_COOLING_LEVEL,
        SensorEntityDescription(
            key="water_cooling_level",
            name="Water cooling level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        Register.SUPPLY_FAN_LEVEL,
        SensorEntityDescription(
            key="supply_fan_level",
            name="Supply fan level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        Register.EXHAUST_FAN_LEVEL,
        SensorEntityDescription(
            key="exhaust_fan_level",
            name="Exhaust fan level",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
)

PLAIN_SENSORS: tuple[tuple[Register, SensorEntityDescription], ...] = (
    (
        Register.VENTILATION_LEVEL_CURRENT,
        SensorEntityDescription(
            key="ventilation_level_current",
            name="Current ventilation level",
        ),
    ),
    (
        Register.OVR_TIME_CURRENT,
        SensorEntityDescription(
            key="ovr_time_remaining",
            name="Boost time remaining",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 sensors."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[KomfoventC4Entity] = [
        ScaledSensor(coordinator, description, register)
        for register, description in TEMPERATURE_SENSORS
    ]
    entities += [
        KomfoventC4Sensor(coordinator, description, register)
        for register, description in PERCENT_SENSORS + PLAIN_SENSORS
    ]
    entities.append(
        StopCodeSensor(
            coordinator,
            SensorEntityDescription(
                key="stop_code",
                name="Stop reason",
                device_class=SensorDeviceClass.ENUM,
                options=[code.name.lower() for code in StopCode],
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            Register.ALARM_STOP_CODE,
        )
    )
    entities.append(
        ClockSensor(
            coordinator,
            SensorEntityDescription(
                key="clock",
                name="Clock",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        )
    )

    async_add_entities(entities)


class KomfoventC4Sensor(KomfoventC4Entity, SensorEntity):
    """A sensor reporting a register's raw value."""

    @property
    def native_value(self) -> int | None:
        """Return the register value."""
        return self.raw_value


class ScaledSensor(KomfoventC4Sensor):
    """A temperature sensor whose register holds tenths of a degree."""

    @property
    def native_value(self) -> float | None:
        """Return the register value in degrees, or None if no sensor is fitted."""
        value = self.raw_value
        if value is None or value == TEMP_NO_SENSOR:
            return None
        return value / 10


class StopCodeSensor(KomfoventC4Sensor):
    """The documented reason the unit stopped itself."""

    @property
    def native_value(self) -> str | None:
        """Return the stop reason as a lowercase enum name."""
        value = self.raw_value
        if value is None:
            return None
        try:
            return StopCode(value).name.lower()
        except ValueError:
            return None


class ClockSensor(KomfoventC4Entity, SensorEntity):
    """
    The controller's own clock, assembled from registers 1002, 1004 and 1005.

    The C4 has no NTP and drifts; this makes the drift visible so the sync
    clock button can be pressed (or automated) when it matters. Resolution is
    one minute — the controller exposes no seconds.

    Deliberately not a TIMESTAMP sensor: the frontend renders those as
    "5 minutes ago", which is useless for a clock. The state is the plain
    ``YYYY-MM-DD HH:MM`` the controller would show on its own panel, in the
    controller's (i.e. local) time; the parsed datetime is an attribute.
    """

    @property
    def native_value(self) -> str | None:
        """Return the controller's clock as ``YYYY-MM-DD HH:MM``."""
        clock = self.clock
        return None if clock is None else clock.strftime("%Y-%m-%d %H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the clock as an ISO timestamp for templates."""
        clock = self.clock
        return None if clock is None else {"timestamp": clock.isoformat()}

    @property
    def clock(self) -> datetime | None:
        """Return the controller's local time as an aware datetime."""
        data = self.coordinator.data
        if not data:
            return None
        try:
            time, month_day, year = (
                data[Register.TIME],
                data[Register.MONTH_DAY],
                data[Register.YEAR],
            )
            naive = datetime(  # noqa: DTZ001 -- localised right below
                year, month_day >> 8, month_day & 0xFF, time >> 8, time & 0xFF
            )
        except (KeyError, ValueError):
            _LOGGER.debug("Controller clock registers do not form a valid date")
            return None
        return naive.replace(tzinfo=dt_util.get_default_time_zone())
