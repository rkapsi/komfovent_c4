"""Binary sensor platform for the Komfovent C4 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import DOMAIN, STOP_FLAG_BITS, WARNING_BITS
from .entity import KomfoventC4Entity
from .registers import Register

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import KomfoventC4Coordinator

WARNING_NAMES = {
    "service": "Service required",
    "heater_off": "Heater off",
    "rotor_stop": "Rotor stopped",
}

STOP_FLAG_NAMES = {
    "supply_sensor_b1": "Supply sensor B1 fault",
    "heater_overheating": "Heater overheating",
    "water_temp_low": "Water temperature low",
    "rotor_stop": "Rotor stopped",
    "frost_possibility": "Frost possibility",
    "air_temp_high": "Air temperature high",
    "air_temp_low": "Air temperature low",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Komfovent C4 binary sensors."""
    coordinator: KomfoventC4Coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[KomfoventC4Entity] = [
        KomfoventC4BinarySensor(
            coordinator,
            BinarySensorEntityDescription(
                key="fans_running",
                name="Fans running",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
            Register.AHU_FANS_STATUS,
        )
    ]

    entities += [
        BitfieldBinarySensor(
            coordinator,
            BinarySensorEntityDescription(
                key=f"warning_{key}",
                name=WARNING_NAMES[key],
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            Register.ALARM_WARNINGS,
            bit=bit,
        )
        for key, bit in WARNING_BITS.items()
    ]

    entities += [
        BitfieldBinarySensor(
            coordinator,
            BinarySensorEntityDescription(
                key=f"stop_{key}",
                name=STOP_FLAG_NAMES[key],
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            Register.ALARM_STOP_FLAGS,
            bit=bit,
        )
        for key, bit in STOP_FLAG_BITS.items()
    ]

    async_add_entities(entities)


class KomfoventC4BinarySensor(KomfoventC4Entity, BinarySensorEntity):
    """A binary sensor reflecting whether a register is non-zero."""

    @property
    def is_on(self) -> bool | None:
        """Return whether the register is non-zero."""
        value = self.raw_value
        return None if value is None else bool(value)


class BitfieldBinarySensor(KomfoventC4BinarySensor):
    """A binary sensor reflecting one bit of an alarm register."""

    def __init__(
        self,
        coordinator: KomfoventC4Coordinator,
        entity_description: BinarySensorEntityDescription,
        register: Register,
        *,
        bit: int,
    ) -> None:
        """Initialize the bitfield binary sensor."""
        super().__init__(coordinator, entity_description, register)
        self.bit = bit

    @property
    def is_on(self) -> bool | None:
        """Return whether this sensor's bit is set."""
        value = self.raw_value
        return None if value is None else bool(value & (1 << self.bit))
