"""Number platform for the Komfovent C4 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)

from .const import (
    CORRECTION_MAX_TEMP,
    CORRECTION_MIN_TEMP,
    DOMAIN,
    INTENSITY_MAX,
    INTENSITY_MIN,
    OVR_TIME_MAX,
    OVR_TIME_MIN,
)
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

INTENSITY_REGISTERS: tuple[tuple[Register, str, str], ...] = (
    (Register.INTAKE_INTENSITY_1, "intake_intensity_1", "Intake intensity level 1"),
    (Register.INTAKE_INTENSITY_2, "intake_intensity_2", "Intake intensity level 2"),
    (Register.INTAKE_INTENSITY_3, "intake_intensity_3", "Intake intensity level 3"),
    (Register.INTAKE_INTENSITY_4, "intake_intensity_4", "Intake intensity level 4"),
    (Register.EXHAUST_INTENSITY_1, "exhaust_intensity_1", "Exhaust intensity level 1"),
    (Register.EXHAUST_INTENSITY_2, "exhaust_intensity_2", "Exhaust intensity level 2"),
    (Register.EXHAUST_INTENSITY_3, "exhaust_intensity_3", "Exhaust intensity level 3"),
    (Register.EXHAUST_INTENSITY_4, "exhaust_intensity_4", "Exhaust intensity level 4"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 numbers."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[KomfoventC4Entity] = [
        KomfoventC4Number(
            coordinator,
            NumberEntityDescription(
                key=key,
                name=name,
                native_min_value=INTENSITY_MIN,
                native_max_value=INTENSITY_MAX,
                native_step=1,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.CONFIG,
            ),
            register,
        )
        for register, key, name in INTENSITY_REGISTERS
    ]

    entities.append(
        KomfoventC4Number(
            coordinator,
            NumberEntityDescription(
                key="boost_duration",
                name="Boost duration",
                native_min_value=OVR_TIME_MIN,
                native_max_value=OVR_TIME_MAX,
                native_step=1,
                native_unit_of_measurement=UnitOfTime.MINUTES,
                device_class=NumberDeviceClass.DURATION,
                entity_category=EntityCategory.CONFIG,
            ),
            Register.OVR_TIME,
        )
    )

    entities.append(
        ScaledNumber(
            coordinator,
            NumberEntityDescription(
                key="temperature_correction_setpoint",
                name="Temperature correction",
                native_min_value=CORRECTION_MIN_TEMP,
                native_max_value=CORRECTION_MAX_TEMP,
                native_step=0.1,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=NumberDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.CONFIG,
            ),
            Register.TEMP_CORRECTION,
        )
    )

    async_add_entities(entities)


class KomfoventC4Number(KomfoventC4Entity, NumberEntity):
    """A writable numeric register."""

    @property
    def native_value(self) -> float | None:
        """Return the register value."""
        value = self.raw_value
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the register."""
        await self.async_write(int(value))


class ScaledNumber(KomfoventC4Number):
    """A writable register holding the value multiplied by ten."""

    @property
    def native_value(self) -> float | None:
        """Return the register value scaled back to real units."""
        value = self.raw_value
        return None if value is None else value / 10

    async def async_set_native_value(self, value: float) -> None:
        """Write the scaled value to the register."""
        await self.async_write(round(value * 10))
