"""Set the charge limit. ONLY when the option 'Allow control' is on.

Make sure nothing else (e.g. another OCPP backend) writes charge limits to the
charger at the same time, or the two will overwrite each other.
"""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugchoiceConfigEntry
from .api import PlugchoiceError
from .const import CONF_ALLOW_CONTROL, DOMAIN
from .entity import PlugchoiceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PlugchoiceConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if not entry.options.get(CONF_ALLOW_CONTROL, False):
        return
    async_add_entities([PlugchoiceChargeLimit(entry.runtime_data.coordinator)])


class PlugchoiceChargeLimit(PlugchoiceEntity, RestoreNumber):
    """Maximum charge current (A) of the connector. 0 = pause charging.

    Plugchoice does not always fill in current_limit of the connector (it stayed null
    in tests). The entity therefore remembers the last value it set, also across a
    restart (RestoreNumber), so 'only write when it changes' automations keep working.
    """

    _attr_translation_key = "set_charge_limit"
    _attr_icon = "mdi:current-ac"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 0
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "laadlimiet_instellen")
        self._last_set: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) is not None:
            self._last_set = last.native_value

    @property
    def native_max_value(self) -> float:
        con = self.coordinator.data.connector
        return float(con.get("max_amperage") or self.coordinator.data.charger.get("max_current") or 32)

    @property
    def native_value(self) -> float | None:
        limit = self.coordinator.data.connector.get("current_limit")
        return float(limit) if limit is not None else self._last_set

    async def async_set_native_value(self, value: float) -> None:
        try:
            # connector_id 0 (whole charger) returns 422 "Cannot find the specified
            # connector", so use the real connector.
            status = await self.coordinator.client.set_charge_limit(
                self.coordinator.charger_uuid, int(value), connector_id=self.coordinator.connector_id
            )
        except PlugchoiceError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_limit_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if status != "Accepted":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_limit_rejected",
                translation_placeholders={"status": str(status), "limit": str(int(value))},
            )
        self._last_set = float(int(value))
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
