"""Config flow for Pandora Car Alarm System component."""
__all__ = ("PandoraCASConfigFlow",)

import logging
from typing import (
    Any,
    Dict,
    Optional,
)

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_ACCESS_TOKEN,
    CONF_DEVICES,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import (
    FlowResult,
    FlowResultType,
)
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
)

from custom_components.pandora_cas import (
    async_run_pandora_coro,
    DEVICE_OPTIONS_SCHEMA,
    BASE_CONFIG_ENTRY_SCHEMA,
    INTEGRATION_OPTIONS_SCHEMA,
)
from custom_components.pandora_cas.api import PandoraOnlineAccount
from custom_components.pandora_cas.const import *

_LOGGER = logging.getLogger(__name__)


async def async_options_flow_init_step_validate(
    handler: SchemaCommonFlowHandler,
    user_input: dict[str, Any],
) -> dict[str, Any]:
    cursor_type = (
        user_input.pop(CONF_CUSTOM_CURSOR_TYPE, None) or DEFAULT_CURSOR_TYPE
    )
    if devices := user_input.pop(CONF_CUSTOM_CURSOR_DEVICES, None):
        custom_cursors = handler.options.setdefault(CONF_CUSTOM_CURSORS, {})
        if cursor_type == DEFAULT_CURSOR_TYPE:
            for device_id in devices:
                custom_cursors.pop(device_id, None)
        else:
            for device_id in devices:
                custom_cursors[device_id] = cursor_type

    return user_input


class PandoraCASConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pandora Car Alarm System config entries."""

    CONNECTION_CLASS: Final[str] = config_entries.CONN_CLASS_CLOUD_PUSH
    VERSION: Final[int] = 10

    def __init__(self) -> None:
        """Init the config flow."""
        self._reauth_entry: Optional[config_entries.ConfigEntry] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is not None:
            account = PandoraOnlineAccount(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                access_token=user_input.get(CONF_ACCESS_TOKEN),
                session=async_get_clientsession(
                    self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
                ),
            )

            try:
                await async_run_pandora_coro(account.async_authenticate())
            except ConfigEntryAuthFailed:
                error = "invalid_auth"
            except ConfigEntryNotReady:
                error = "cannot_connect"
            else:
                unique_id = str(account.user_id)
                if entry := self._reauth_entry:
                    # Handle reauthentication
                    if unique_id != self._reauth_entry.unique_id:
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()

                    self.hass.config_entries.async_update_entry(
                        entry,
                        title=user_input[CONF_USERNAME],
                        unique_id=unique_id,
                        data={
                            **entry.data,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCESS_TOKEN: account.access_token,
                        },
                        options={
                            **entry.options,
                            CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                else:
                    # Handle new config entry
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    user_input[CONF_ACCESS_TOKEN] = account.access_token

                    options = {
                        str(option): user_input.pop(str(option))
                        for option in INTEGRATION_OPTIONS_SCHEMA.schema
                    }

                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data=user_input,
                        options=options,
                    )

            errors = {"base": error}
            schema = self.add_suggested_values_to_schema(
                BASE_CONFIG_ENTRY_SCHEMA,
                user_input,
            )
        elif entry := self._reauth_entry:
            errors = {"base": "invalid_auth"}
            schema = self.add_suggested_values_to_schema(
                BASE_CONFIG_ENTRY_SCHEMA,
                {**entry.data, **entry.options, CONF_PASSWORD: ""},
            )
        else:
            errors = None
            schema = BASE_CONFIG_ENTRY_SCHEMA

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_step_import(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        if user_input is None:
            _LOGGER.error("Called import step without configuration")
            return self.async_abort("empty_configuration_import")

        result = await self.async_step_user(user_input)
        return (
            result
            if result["type"] == FlowResultType.CREATE_ENTRY
            else self.async_abort("unknown")
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PandoraCASOptionsFlow(config_entry)


STEP_DEVICE_OPTIONS: Final = "device_options"
STEP_INTEGRATION_OPTIONS: Final = "integration_options"
STEP_SAVE: Final = "save"


class PandoraCASOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.device_options: Optional[dict[str, str]] = None
        self.current_pandora_id: str | None = None
        self.save_needed = False
        self.options[
            CONF_DISABLE_POLLING
        ] = self.config_entry.pref_disable_polling

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        menu_options = [STEP_INTEGRATION_OPTIONS, STEP_DEVICE_OPTIONS]
        if self.save_needed:
            menu_options.append(STEP_SAVE)
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        disable_polling = self.options.pop(CONF_DISABLE_POLLING)

        if disable_polling != self.config_entry.pref_disable_polling:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options=self.options,
                pref_disable_polling=disable_polling,
            )
        return self.async_create_entry(title="", data=self.options)

    async def async_step_device_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if (pandora_id := self.current_pandora_id) is None:
            if self.device_options is None:
                self.device_options = {}
                dev_reg = device_registry.async_get(self.hass)
                for device in dev_reg.devices.values():
                    for identifier in device.identifiers:
                        if len(identifier) != 2 or identifier[0] != DOMAIN:
                            continue
                        self.device_options[
                            str(identifier[1])
                        ] = f"{device.name} ({identifier[1]})"

                for pandora_id in self.options.get(CONF_DEVICES) or {}:
                    self.device_options.setdefault(
                        str(pandora_id), f"<unknown> ({pandora_id})"
                    )

            return self.async_show_menu(
                step_id=STEP_DEVICE_OPTIONS, menu_options=self.device_options
            )

        schema = DEVICE_OPTIONS_SCHEMA

        if user_input is None:
            schema = self.add_suggested_values_to_schema(
                schema, self.options.get(CONF_DEVICES, {}).get(pandora_id, {})
            )
        else:
            self.options.setdefault(CONF_DEVICES, {}).setdefault(
                pandora_id, {}
            ).update(user_input)
            self.current_pandora_id = None
            self.save_needed = True
            return await self.async_step_init()

        return self.async_show_form(
            step_id=STEP_DEVICE_OPTIONS, data_schema=schema
        )

    async def async_step_integration_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        schema = INTEGRATION_OPTIONS_SCHEMA

        if user_input is None:
            schema = self.add_suggested_values_to_schema(schema, self.options)
        else:
            self.options.update(user_input)
            self.save_needed = True
            return await self.async_step_init()

        return self.async_show_form(
            step_id=STEP_INTEGRATION_OPTIONS, data_schema=schema
        )

    def __getattr__(self, attribute):
        if isinstance(attribute, str) and attribute.startswith("async_step_"):
            pandora_id = attribute[11:]
            if pandora_id.isnumeric():
                self.current_pandora_id = pandora_id
                return self.async_step_device_options
        raise AttributeError
