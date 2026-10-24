"""Set up via the UI: enter a token, choose the charger; options for interval and control."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import PlugchoiceAuthError, PlugchoiceClient, PlugchoiceError
from .const import (
    CONF_ALLOW_CONTROL,
    CONF_CHARGER_UUID,
    CONF_CONNECTOR_ID,
    CONF_ID_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_CONNECTOR_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

TOKEN_SCHEMA = vol.Schema(
    {vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


def _label(charger: dict[str, Any]) -> str:
    model = (charger.get("model") or {}).get("name") or "Charger"
    return f"{model} ({charger.get('reference') or charger.get('uuid', '')[:8]})"


class PlugchoiceConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._token: str | None = None
        self._chargers: list[dict[str, Any]] = []

    async def _fetch_chargers(self, token: str) -> list[dict[str, Any]]:
        client = PlugchoiceClient(async_get_clientsession(self.hass), token)
        return await client.get_chargers()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                chargers = await self._fetch_chargers(user_input[CONF_TOKEN])
            except PlugchoiceAuthError:
                errors["base"] = "invalid_auth"
            except PlugchoiceError:
                errors["base"] = "cannot_connect"
            else:
                if not chargers:
                    return self.async_abort(reason="no_chargers")
                self._token = user_input[CONF_TOKEN]
                self._chargers = chargers
                if len(chargers) == 1:
                    return await self._create(chargers[0])
                return await self.async_step_charger()
        return self.async_show_form(step_id="user", data_schema=TOKEN_SCHEMA, errors=errors)

    async def async_step_charger(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            charger = next(c for c in self._chargers if c["uuid"] == user_input[CONF_CHARGER_UUID])
            return await self._create(charger)
        options = [{"value": c["uuid"], "label": _label(c)} for c in self._chargers]
        return self.async_show_form(
            step_id="charger",
            data_schema=vol.Schema(
                {vol.Required(CONF_CHARGER_UUID): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def _create(self, charger: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(charger["uuid"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Plugchoice – {_label(charger)}",
            data={
                CONF_TOKEN: self._token,
                CONF_CHARGER_UUID: charger["uuid"],
                CONF_CONNECTOR_ID: DEFAULT_CONNECTOR_ID,
            },
            # Deliberately: control is OFF by default.
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_ALLOW_CONTROL: False},
        )

    # ---------------------------------------------------- new token (401)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._fetch_chargers(user_input[CONF_TOKEN])
            except PlugchoiceAuthError:
                errors["base"] = "invalid_auth"
            except PlugchoiceError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )
        return self.async_show_form(step_id="reauth_confirm", data_schema=TOKEN_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return PlugchoiceOptionsFlow()


class PlugchoiceOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input.get(CONF_ID_TOKEN):
                user_input.pop(CONF_ID_TOKEN, None)
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=5,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_ALLOW_CONTROL, default=opts.get(CONF_ALLOW_CONTROL, False)
                ): BooleanSelector(),
                vol.Optional(
                    CONF_ID_TOKEN, description={"suggested_value": opts.get(CONF_ID_TOKEN)}
                ): TextSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
