# Changelog

## 0.3.0 – 2026-10-24

First public release.

- Entity and device names come from translations (English and Dutch). Unique IDs
  are unchanged, so existing installations keep their entity IDs; with Home Assistant
  in Dutch the names are the same as before.
- State attributes in English: `error`, `error_info`, `updated_at_ms`, `measured_at`,
  `active`, `stop_reason`, `managed_by`, `min_current`, `power_type`.
- Error messages are translated.
- Log messages, comments and documentation in English.
- `tools/probe.py` reads the token from `PLUGCHOICE_TOKEN`.
- HACS support, hassfest and HACS validation on GitHub Actions.

## 0.2.0 – 2026-10-04

- Charge limit uses connector 1: `connector_id: 0` (the whole charger, according to
  the docs) returned 422 "Cannot find the specified connector".
- *Set charge limit* remembers the last value it set (RestoreNumber) when Plugchoice
  does not report `current_limit`.
- An error while fetching transactions (the API has returned 500) no longer fails the
  rest of the update; the previous session is kept.

## 0.1.0 – 2026-10-03

First version.

- Config flow with personal access token, charger selection and reauthentication.
- Read entities: status, power, current per phase, offered current, energy meter,
  session energy and times, Plugchoice charge limit, voltage, temperature, diagnostics.
- Control (charge limit, start/stop) only with the option *Allow control*, off by
  default. The API client also refuses writes without it.
- Diagnostics without token, pin code, serial number, RFID and address.
- Test script `tools/probe.py` (read-only).
