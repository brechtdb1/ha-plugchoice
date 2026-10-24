"""Test script for the Plugchoice integration, outside Home Assistant.

Uses the same api.py as the integration. Handy to quickly see what still works after
an API change at Plugchoice, or to check what your charger reports before installing.

READ-ONLY: the script only calls GET endpoints. The token is read from the environment
variable PLUGCHOICE_TOKEN and never printed. Pin code, serial number and RFID tags are
not printed either.

Usage (from the root of the repository):
    pip install aiohttp
    PLUGCHOICE_TOKEN=... python tools/probe.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "plugchoice"


def _load(name: str):
    """Load const.py and api.py without importing the HA package (__init__.py)."""
    spec = importlib.util.spec_from_file_location(f"plugchoice.{name}", PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"plugchoice.{name}"] = module
    spec.loader.exec_module(module)
    return module


sys.modules.setdefault("plugchoice", type(sys)("plugchoice"))
sys.modules["plugchoice"].__path__ = [str(PKG)]
_load("const")
api = _load("api")


def _token() -> str:
    token = os.environ.get("PLUGCHOICE_TOKEN", "").strip()
    if not token:
        sys.exit("Set the environment variable PLUGCHOICE_TOKEN to a Plugchoice personal access token")
    return token


async def main() -> None:
    import aiohttp

    async with aiohttp.ClientSession() as session:
        client = api.PlugchoiceClient(session, _token())  # allow_control=False
        chargers = await client.get_chargers()
        print(f"{len(chargers)} charger(s) on this account")
        for ch in chargers:
            uuid = ch["uuid"]
            detail = await client.get_charger(uuid)
            con = (detail.get("connectors") or [{}])[0]
            cid = con.get("connector_id", 1)
            print(f"\nCharger {uuid}")
            print(f"  model        {(detail.get('model') or {}).get('vendor')} {(detail.get('model') or {}).get('name')}")
            print(f"  connection   {detail.get('connection_status')}  heartbeat {detail.get('last_heartbeat_at')}")
            print(f"  connector {cid}  status {con.get('status')}  max {con.get('max_amperage')} A  "
                  f"min {con.get('min_current')} A  limit {con.get('current_limit')} ({con.get('current_limit_managed_by')})")
            pu = await client.get_power_usage(uuid, cid)
            print(f"  power-usage  {pu.get('kW')} kW  L1 {pu.get('L1')}  L2 {pu.get('L2')}  L3 {pu.get('L3')} A")
            mv = await client.get_latest_meter_value(uuid, cid)
            for entry in mv.get("meterValue", [])[:1]:
                print(f"  metervalue   {entry.get('timestamp')}")
                for s in entry.get("sampledValue", []):
                    print(f"    {s.get('measurand'):<32} {s.get('phase') or '':<5} {s.get('value'):>10} {s.get('unit')}")
            tx = await client.get_transactions(uuid)
            if tx:
                t = tx[0]
                print(f"  last session {t.get('started_at')} -> {t.get('stopped_at') or 'running'}  {t.get('total_kwh')} kWh")
        # Check: writing must be refused without allow_control.
        try:
            await client.set_charge_limit("test", 6)
        except api.PlugchoiceControlDisabled as err:
            print(f"\nSafety check OK: {err}")


if __name__ == "__main__":
    asyncio.run(main())
