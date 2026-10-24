"""Coordinator: fetches all data of one charger every scan_interval.

Each round sends 4 GET requests to the API: charger (with connectors), power-usage,
latest-metervalue and transactions. At 30 s that is 8 per minute; the Plugchoice limit
is 500 per minute per user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PlugchoiceAuthError, PlugchoiceClient, PlugchoiceError, PlugchoiceRateLimited
from .const import (
    CONF_CHARGER_UUID,
    CONF_CONNECTOR_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONNECTOR_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlugchoiceData:
    """Snapshot of one charger."""

    charger: dict[str, Any]
    connector: dict[str, Any]
    power_usage: dict[str, Any]
    meter_values: dict[str, float] = field(default_factory=dict)  # measurand -> value
    meter_timestamp: str | None = None
    last_transaction: dict[str, Any] | None = None

    @property
    def status(self) -> str | None:
        return self.connector.get("status")

    @property
    def transaction_active(self) -> bool:
        tx = self.last_transaction
        return bool(tx) and tx.get("stopped_at") is None


class PlugchoiceCoordinator(DataUpdateCoordinator[PlugchoiceData]):
    """Polls the Plugchoice API for one charger."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: PlugchoiceClient) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.charger_uuid: str = entry.data[CONF_CHARGER_UUID]
        self.connector_id: int = entry.data.get(CONF_CONNECTOR_ID, DEFAULT_CONNECTOR_ID)

    async def _async_update_data(self) -> PlugchoiceData:
        try:
            charger = await self.client.get_charger(self.charger_uuid)
            power = await self.client.get_power_usage(self.charger_uuid, self.connector_id)
            meter = await self.client.get_latest_meter_value(self.charger_uuid, self.connector_id)
        except PlugchoiceAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PlugchoiceRateLimited as err:
            raise UpdateFailed(f"Plugchoice rate limit, retry after {err.retry_after} s") from err
        except PlugchoiceError as err:
            raise UpdateFailed(str(err)) from err

        # Transactions are secondary: an error there (the API has returned 500 before)
        # must not fail the rest of the round. Keep the previous session instead.
        try:
            transactions = await self.client.get_transactions(self.charger_uuid)
            last_tx = transactions[0] if transactions else None
        except PlugchoiceAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PlugchoiceError as err:
            _LOGGER.debug("Could not fetch transactions: %s", err)
            last_tx = self.data.last_transaction if self.data else None

        connector = next(
            (c for c in charger.get("connectors", []) if c.get("connector_id") == self.connector_id),
            {},
        )

        values: dict[str, float] = {}
        timestamp = None
        entries = (meter.get("meterValue") or []) if isinstance(meter, dict) else []
        if entries:
            timestamp = entries[0].get("timestamp")
            for sample in entries[0].get("sampledValue", []):
                measurand = sample.get("measurand") or "Energy.Active.Import.Register"
                phase = sample.get("phase")
                key = f"{measurand}.{phase}" if phase else measurand
                try:
                    value = float(sample.get("value"))
                except (TypeError, ValueError):
                    continue
                # Wh -> kWh and W -> kW; A, V and Celsius stay as they are.
                if sample.get("unit") in ("Wh", "W"):
                    value /= 1000
                values[key] = value

        return PlugchoiceData(
            charger=charger,
            connector=connector,
            power_usage=power if isinstance(power, dict) else {},
            meter_values=values,
            meter_timestamp=timestamp,
            last_transaction=last_tx,
        )
