"""Small async client for the Plugchoice API (v3).

Deliberately independent of Home Assistant (aiohttp only), so it can also be tested
on its own with tools/probe.py.

Safety: write commands (charge limit, start, stop) only go through when the client was
created with ``allow_control=True``. Otherwise PlugchoiceControlDisabled is raised
before anything is sent to the API, so the charger cannot be controlled by accident
while something else (e.g. another OCPP backend) is in charge of it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, USER_AGENT

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class PlugchoiceError(Exception):
    """General Plugchoice API error."""


class PlugchoiceAuthError(PlugchoiceError):
    """Token invalid or revoked (HTTP 401/403 from the API itself)."""


class PlugchoiceRateLimited(PlugchoiceError):
    """HTTP 429. ``retry_after`` is the number of seconds from the Retry-After header."""

    def __init__(self, retry_after: int | None) -> None:
        super().__init__(f"Rate limit reached, retry after {retry_after} s")
        self.retry_after = retry_after


class PlugchoiceControlDisabled(PlugchoiceError):
    """A write command while 'Allow control' is off."""


class PlugchoiceClient:
    """Access to one Plugchoice account with a personal access token."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        *,
        allow_control: bool = False,
        base_url: str = API_BASE_URL,
    ) -> None:
        self._session = session
        self._token = token
        self._base_url = base_url.rstrip("/")
        self.allow_control = allow_control

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method, url, headers=headers, json=json, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 429:
                    retry = resp.headers.get("Retry-After")
                    raise PlugchoiceRateLimited(int(retry) if retry and retry.isdigit() else None)
                if resp.status in (401, 403):
                    body = await resp.text()
                    # Cloudflare also returns 403, but with its own error page: that is
                    # not a token problem and must not start a reauthentication.
                    if "cloudflare" in body.lower():
                        raise PlugchoiceError(f"Request blocked by Cloudflare ({resp.status})")
                    raise PlugchoiceAuthError(f"Token rejected ({resp.status})")
                if resp.status >= 400:
                    body = await resp.text()
                    raise PlugchoiceError(f"{method} {path} returned {resp.status}: {body[:200]}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise PlugchoiceError(f"{method} {path} failed: {err}") from err

    # ------------------------------------------------------------------ read

    async def get_user(self) -> dict[str, Any]:
        return await self._request("GET", "/user")

    async def get_chargers(self) -> list[dict[str, Any]]:
        """All chargers of the account (first page, max. 25)."""
        data = await self._request("GET", "/chargers")
        return data.get("data", [])

    async def get_charger(self, charger: str) -> dict[str, Any]:
        """Charger with status, connection, max. current and the connectors."""
        data = await self._request("GET", f"/chargers/{charger}")
        return data.get("data", data)

    async def get_power_usage(self, charger: str, connector_id: int) -> dict[str, Any]:
        """Power (kW) and current per phase (L1-L3) of the last measurement."""
        return await self._request("GET", f"/chargers/{charger}/connectors/{connector_id}/power-usage")

    async def get_latest_meter_value(self, charger: str, connector_id: int) -> dict[str, Any]:
        """Latest OCPP MeterValues (e.g. Energy.Active.Import.Register in Wh)."""
        return await self._request(
            "GET", f"/chargers/{charger}/connectors/{connector_id}/latest-metervalue"
        )

    async def get_transactions(self, charger: str) -> list[dict[str, Any]]:
        """Last 15 charging sessions, newest first."""
        data = await self._request("GET", f"/chargers/{charger}/transactions")
        return data.get("data", [])

    # ----------------------------------------------------------------- write

    def _check_control(self, action: str) -> None:
        if not self.allow_control:
            raise PlugchoiceControlDisabled(
                f"'{action}' refused: 'Allow control' is off in the options"
            )

    async def set_charge_limit(self, charger: str, limit: float, connector_id: int = 1) -> str:
        """Charge limit in A (0 = pause). According to the docs connector_id 0 is the
        whole charger, but the API then answers 422; use the real connector (1)."""
        self._check_control("charge limit")
        _LOGGER.info("Plugchoice: charge limit %s A (connector %s)", limit, connector_id)
        data = await self._request(
            "POST",
            f"/chargers/{charger}/actions/charge-limit",
            {"connector_id": connector_id, "limit": limit},
        )
        return data.get("status", "Unknown") if isinstance(data, dict) else str(data)

    async def start_charging(self, charger: str, id_token: str, connector_id: int | None = None) -> str:
        self._check_control("start charging")
        body: dict[str, Any] = {"id_token": id_token}
        if connector_id:
            body["connector_id"] = connector_id
        data = await self._request("POST", f"/chargers/{charger}/actions/start", body)
        return data.get("status", "Unknown") if isinstance(data, dict) else str(data)

    async def stop_charging(self, charger: str) -> str:
        self._check_control("stop charging")
        data = await self._request("POST", f"/chargers/{charger}/actions/stop", {})
        return data.get("status", "Unknown") if isinstance(data, dict) else str(data)
