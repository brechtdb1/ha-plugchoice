"""Constants for the Plugchoice integration."""

from __future__ import annotations

DOMAIN = "plugchoice"

# Plugchoice API (v3). The examples in the official documentation use
# app.plugchoice.com/api/v3; api.plugchoice.com/v3 works as well.
API_BASE_URL = "https://app.plugchoice.com/api/v3"

# The Cloudflare front of the API blocks the default User-Agents of HTTP libraries
# (error 1010 "browser_signature_banned"), so always send our own.
USER_AGENT = "HomeAssistant-Plugchoice/0.4 (+https://github.com/brechtdb1/ha-plugchoice)"

CONF_TOKEN = "token"
CONF_CHARGER_UUID = "charger_uuid"
CONF_CONNECTOR_ID = "connector_id"

# Options (Settings → Devices & services → Plugchoice → Configure)
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ALLOW_CONTROL = "allow_control"
CONF_ID_TOKEN = "id_token"

DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 300
DEFAULT_CONNECTOR_ID = 1

# OCPP 1.6 connector statuses that mean a cable/car is connected.
PLUGGED_STATUSES = {"Preparing", "Charging", "SuspendedEV", "SuspendedEVSE", "Finishing"}
CHARGING_STATUS = "Charging"
OCPP_STATUSES = [
    "Available",
    "Preparing",
    "Charging",
    "SuspendedEV",
    "SuspendedEVSE",
    "Finishing",
    "Reserved",
    "Unavailable",
    "Faulted",
]

# Fields that must never appear in logs or diagnostics.
REDACT_KEYS = {
    "token",
    "pincode",
    "serial_number",
    "identity",
    "id_tag",
    "id_token",
    "serialNumber",
    "address",
    "street",
    "house_number",
    "postal_code",
    "city",
    "latitude",
    "longitude",
    "websocket_url",
}
