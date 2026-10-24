"""Start/stop charging. ONLY when the option 'Allow control' is on.

'Start charging' needs an ID token (RFID/Plug & Charge token); fill it in the
options. Without a token that button is not created.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugchoiceConfigEntry
from .api import PlugchoiceError
from .const import CONF_ALLOW_CONTROL, CONF_ID_TOKEN, DOMAIN
from .entity import PlugchoiceEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PlugchoiceConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    if not entry.options.get(CONF_ALLOW_CONTROL, False):
        return
    coordinator = entry.runtime_data.coordinator
    entities: list[ButtonEntity] = [PlugchoiceStopButton(coordinator)]
    if id_token := entry.options.get(CONF_ID_TOKEN):
        entities.append(PlugchoiceStartButton(coordinator, id_token))
    async_add_entities(entities)


async def _run(coordinator, coro, action: str) -> None:
    """action = start or stop; picks the translated error messages."""
    try:
        status = await coro
    except PlugchoiceError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=f"{action}_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    if status != "Accepted":
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=f"{action}_rejected",
            translation_placeholders={"status": str(status)},
        )
    await coordinator.async_request_refresh()


class PlugchoiceStartButton(PlugchoiceEntity, ButtonEntity):
    _attr_translation_key = "start_charging"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator, id_token: str) -> None:
        super().__init__(coordinator, "laden_starten")
        self._id_token = id_token

    async def async_press(self) -> None:
        c = self.coordinator
        await _run(
            c,
            c.client.start_charging(c.charger_uuid, self._id_token, c.connector_id),
            "start",
        )


class PlugchoiceStopButton(PlugchoiceEntity, ButtonEntity):
    _attr_translation_key = "stop_charging"
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "laden_stoppen")

    async def async_press(self) -> None:
        c = self.coordinator
        await _run(c, c.client.stop_charging(c.charger_uuid), "stop")
