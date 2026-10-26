<img src="custom_components/plugchoice/brand/logo.png" alt="Plugchoice" height="64">

# Plugchoice for Home Assistant

[![Validate](https://github.com/brechtdb1/ha-plugchoice/actions/workflows/validate.yml/badge.svg)](https://github.com/brechtdb1/ha-plugchoice/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

Custom integration that reads (and optionally controls) an EV charger through the
[Plugchoice](https://www.plugchoice.com/) cloud API.

> **Unofficial.** This integration is not made or supported by Plugchoice /
> [Volt Time](https://volttime.com/). It uses their public
> [developer API](https://developer.plugchoice.com/) with your own personal access token.
> Volt Time is fine with this integration for **personal (private) use**; for anything
> else, contact them first. Their terms: [volttime.com/legal](https://volttime.com/legal/).
>
> The Plugchoice name and logo belong to Volt Time and are used with their permission.

## How it works

```
                 every 30 s (configurable)
Home Assistant ───────── HTTPS GET ─────────► app.plugchoice.com/api/v3 ◄──OCPP── Charger
 plugchoice integration ◄──── JSON ──────────
```

- Home Assistant **polls** the API. No ports need to be opened.
- 4 GET requests per round: charger + connectors, power usage, latest meter values,
  sessions. At 30 s that is 8 per minute; the Plugchoice limit is 500 per minute.
- **Read-only by default.** The entities to control the charger only exist once you
  enable *Allow control* in the options, and the API client itself refuses write
  commands without it. Two locks, so nothing is changed by accident.

## Tested with

| Charger | Firmware | Notes |
|---|---|---|
| Volt Time One (3-phase, 20 A, one connector) | 0.10.2 | Read and control |

Other chargers on Plugchoice should work as long as they report OCPP 1.6 status and
meter values, but they have not been tested. Reports (working or not) are welcome in
the [issues](https://github.com/brechtdb1/ha-plugchoice/issues), ideally with the
diagnostics file.

## Installation

### HACS (recommended)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/brechtdb1/ha-plugchoice`,
   category *Integration*.
2. Install **Plugchoice** and restart Home Assistant.

### Manual

Copy `custom_components/plugchoice/` to the `custom_components/` folder of your
configuration and restart Home Assistant.

## Setup

1. In the Plugchoice portal: *Settings → Personal access tokens* → create a token.
2. In Home Assistant: *Settings → Devices & services → Add integration → Plugchoice*,
   and paste the token.
3. If the account has one charger, it is chosen automatically; otherwise pick one.
   Add the integration again for a second charger.

If the token is revoked later, Home Assistant asks for a new one (reauthentication).

### Options

*Settings → Devices & services → Plugchoice → Configure*. The integration reloads by
itself after a change.

| Option | Default | Meaning |
|---|---|---|
| Polling interval | 30 s | 15–300 s. While charging the charger sends new meter values every ~20 s, so polling faster than that does not help. |
| Allow control | **off** | Creates *Set charge limit* and *Stop charging*. Only enable this when nothing else (e.g. another OCPP backend) controls the charger, or they will overwrite each other's limits. |
| ID token | empty | Needed for the *Start charging* button (RFID or Plug & Charge token). Without it there is no start button. |

## Entities

Entity IDs depend on the language of your Home Assistant; in English they start with
`…plugchoice_charger_`.

| Entity | Source (API) | Notes |
|---|---|---|
| Status | connector `status` | OCPP status: Available, Preparing, Charging, SuspendedEV, SuspendedEVSE, Finishing, … Attributes `error`, `error_info`. |
| Power | power-usage `kW` | 0 when no car is connected |
| Current L1 / L2 / L3 | power-usage `L1`–`L3` | 0 without a car (the API otherwise keeps the last value) |
| Current offered | MeterValues `Current.Offered` | **The limit the charger really applies**, whoever set it. Only during a session. |
| Energy total | MeterValues `Energy.Active.Import.Register` | kWh meter reading, suitable for the Energy dashboard. Outside a session updated every 15 minutes. |
| Session energy | transactions `total_kwh` | Running or last session. Attributes `active`, `stop_reason`. |
| Session started / stopped | transactions | Timestamps |
| Charge limit | connector `current_limit` | Only a limit set by **Plugchoice or the API**. Attribute `managed_by`. |
| Voltage L1 / L2 / L3, Temperature | MeterValues | Diagnostic, only during a session |
| Maximum current, Last heartbeat, Firmware | charger | Diagnostic |
| Online | `connection_status` | Diagnostic |
| Car connected | status is Preparing … Finishing | |
| Charging | status is Charging | |
| Set charge limit (number) | `POST …/actions/charge-limit` | **Only with *Allow control*.** 0 = pause; max = maximum current of the charger. Remembers the last value it set (the API does not always report it). |
| Stop charging / Start charging (buttons) | `POST …/actions/stop` / `start` | **Only with *Allow control*** (start also needs the ID token) |

Translations: English and Dutch. Entity names follow the language of the Home Assistant
server (*Settings → System → General*), not that of your user profile.

### Not (yet) supported

- **More than one connector**: the integration always uses connector 1.
- **Plugchoice settings** such as load balancing, smart charging, schedules and tariffs.
- **Session history**: only the running or last session.
- **More than 25 chargers on one account**: only the first page is read.
- RFID card management, reservations and firmware updates.

Pull requests are welcome.

### Example: solar charging

The *Set charge limit* entity is meant to be driven by your own automations, for
example to follow solar surplus. Only write when the value changes, to avoid sending
the same command every minute:

```yaml
- action: number.set_value
  target:
    entity_id: number.plugchoice_charger_set_charge_limit
  data:
    value: "{{ new_limit }}"
```

A charger always applies the lowest of all limits it has (OCPP backend, Plugchoice,
API). If you also use an OCPP integration, set its limit to the maximum.

## API endpoints used

Base: `https://app.plugchoice.com/api/v3`, header `Authorization: Bearer <token>`.

| Method | Path | Used for |
|---|---|---|
| GET | `/chargers` | Config flow: chargers of the account |
| GET | `/chargers/{uuid}` | Status, connection, firmware, connectors |
| GET | `/chargers/{uuid}/connectors/{id}/power-usage` | Power and current per phase |
| GET | `/chargers/{uuid}/connectors/{id}/latest-metervalue` | Meter reading, voltage, temperature, offered current |
| GET | `/chargers/{uuid}/transactions` | Last 15 sessions (newest first) |
| POST | `/chargers/{uuid}/actions/charge-limit` | `{"connector_id": 1, "limit": <A>}` (control only) |
| POST | `/chargers/{uuid}/actions/start` / `stop` | (control only) |

## Good to know

- **Cloudflare blocks default User-Agents** (error 1010, HTTP 403), so the client always
  sends its own. A 403 *with* a Cloudflare page is not a token problem and does not
  trigger reauthentication.
- **Freshness:** without a session the charger only sends a meter reading every 15
  minutes; while charging every ~20 s. A new charge limit applies within ~15–20 s.
- `connector_id: 0` (the whole charger, according to the docs) returns **422** for
  *Set charge limit*; the integration uses the real connector.
- Some GETs (settings, firmware) take 1–5 s because Plugchoice asks the charger; the
  integration does not use them.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Entities `unavailable`, log: `Request blocked by Cloudflare` | Cloudflare refuses the User-Agent; please open an issue |
| *Reauthentication required* | Token revoked: create a new token in the portal and follow the notification |
| Log: `rate limit` | Interval too short, or the same token used elsewhere; raise the interval |
| Current per phase stays 0 while charging | Status is not Preparing … Finishing; check the Status entity |

**Diagnostics:** *Settings → Devices & services → Plugchoice → ⋮ → Download diagnostics*.
Token, pin code, serial number, RFID tags and address data are removed.

## Testing outside Home Assistant

`tools/probe.py` uses the same API client, read-only:

```bash
pip install aiohttp
PLUGCHOICE_TOKEN=... python tools/probe.py
```

It prints the charger, connector, power usage, meter values and the last session, and
checks that writing is refused.

## License

The code is licensed under the [GNU General Public License v3.0 or later](LICENSE):
you may use, change and share it, but modified versions you distribute must stay open
source under the same license. Versions up to 0.3.2 were released under MIT.

The Plugchoice name and the images in `custom_components/plugchoice/brand/` are
trademarks of Volt Time and are **not** covered by the GPL. They are included
with Volt Time's permission, only to show the integration in Home Assistant.
