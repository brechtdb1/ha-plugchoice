"""Base class for all Plugchoice entities: one device per charger."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlugchoiceCoordinator


class PlugchoiceEntity(CoordinatorEntity[PlugchoiceCoordinator]):
    """Shared device info. Entity names come from the translations (translation_key)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PlugchoiceCoordinator, key: str) -> None:
        super().__init__(coordinator)
        uuid = coordinator.charger_uuid
        # The key is part of the unique_id, so it never changes, even where it is
        # Dutch (the integration started out as a Dutch-only build).
        self._attr_unique_id = f"{uuid}_{key}"
        charger = coordinator.data.charger if coordinator.data else {}
        model = charger.get("model") or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uuid)},
            translation_key="charger",
            manufacturer=model.get("vendor") or "Plugchoice",
            model=model.get("name"),
            sw_version=charger.get("parsed_firmware_version"),
            configuration_url="https://app.plugchoice.com/",
        )
