"""Binary sensors: online, car connected, charging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugchoiceConfigEntry
from .const import CHARGING_STATUS, PLUGGED_STATUSES
from .coordinator import PlugchoiceData
from .entity import PlugchoiceEntity


@dataclass(frozen=True, kw_only=True)
class PlugchoiceBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[PlugchoiceData], bool | None]


BINARY_SENSORS: tuple[PlugchoiceBinaryDescription, ...] = (
    PlugchoiceBinaryDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: d.charger.get("connection_status") == "online",
    ),
    PlugchoiceBinaryDescription(
        key="kabel",
        translation_key="car_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=lambda d: d.status in PLUGGED_STATUSES,
    ),
    PlugchoiceBinaryDescription(
        key="laden",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda d: d.status == CHARGING_STATUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PlugchoiceConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(PlugchoiceBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class PlugchoiceBinarySensor(PlugchoiceEntity, BinarySensorEntity):
    entity_description: PlugchoiceBinaryDescription

    def __init__(self, coordinator, description: PlugchoiceBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data)
