"""Plugchoice: Home Assistant integration for an EV charger via the Plugchoice cloud API
(https://developer.plugchoice.com/).

Unofficial; not affiliated with Plugchoice. See README.md in the repository.

READ-ONLY by default. Control (charge limit, start/stop) stays off until you enable
it explicitly in the options of the integration.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PlugchoiceClient
from .const import CONF_ALLOW_CONTROL, CONF_TOKEN
from .coordinator import PlugchoiceCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,  # entities only when 'Allow control' is on
    Platform.BUTTON,  # idem
]


@dataclass
class PlugchoiceRuntimeData:
    client: PlugchoiceClient
    coordinator: PlugchoiceCoordinator


type PlugchoiceConfigEntry = ConfigEntry[PlugchoiceRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: PlugchoiceConfigEntry) -> bool:
    client = PlugchoiceClient(
        async_get_clientsession(hass),
        entry.data[CONF_TOKEN],
        allow_control=entry.options.get(CONF_ALLOW_CONTROL, False),
    )
    coordinator = PlugchoiceCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = PlugchoiceRuntimeData(client, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Options changed (interval, control) -> reload the integration.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: PlugchoiceConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PlugchoiceConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
