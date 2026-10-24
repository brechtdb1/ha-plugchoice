"""Diagnostics (Settings → Devices & services → Plugchoice → ⋮ → Download diagnostics).

Token, pin code, serial number, RFID tags and address data are redacted.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PlugchoiceConfigEntry
from .const import REDACT_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlugchoiceConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, REDACT_KEYS),
        "allow_control": entry.runtime_data.client.allow_control,
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(asdict(coordinator.data), REDACT_KEYS) if coordinator.data else None,
    }
