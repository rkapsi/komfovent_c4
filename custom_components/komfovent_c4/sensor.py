"""Sensor platform for the Komfovent C4 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime

from .const import DOMAIN, StopCode
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

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

    async_add_entities(entities)


class KomfoventC4Sensor(KomfoventC4Entity, SensorEntity):
    """A sensor reporting a register's raw value."""

    @property
    def native_value(self) -> int | None:
        """Return the register value."""
        return self.raw_value


class ScaledSensor(KomfoventC4Sensor):
    """A sensor whose register holds the value multiplied by ten."""

    @property
    def native_value(self) -> float | None:
        """Return the register value scaled back to real units."""
        value = self.raw_value
        return None if value is None else value / 10


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
