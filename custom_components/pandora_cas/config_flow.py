"""Config flow for Pandora Car Alarm System component."""

__all__ = ("PandoraCASConfigFlow",)

import logging
from copy import deepcopy
from json import dumps
from typing import Any, Final

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import (
    OptionsFlowWithConfigEntry,
    ConfigFlow,
    ConfigEntry,
    OptionsFlow,
    SOURCE_IMPORT,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_ACCESS_TOKEN,
    CONF_DEVICES,
    CONF_METHOD,
    CONF_LANGUAGE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import (
    FlowResult,
    FlowResultType,
)
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.translation import async_get_translations

from custom_components.pandora_cas import (
    async_run_pandora_coro,
    ENTRY_DATA_SCHEMA,
    BASE_INTEGRATION_OPTIONS_SCHEMA,
    DEVICE_OPTIONS_SCHEMA,
)
from custom_components.pandora_cas.const import (
    METHOD_COMBO,
    CONF_DISABLE_WEBSOCKETS,
    METHOD_MANUAL,
    METHOD_POLL,
    METHOD_LISTEN,
    DOMAIN,
    CONF_IGNORE_UPDATES_ENGINE_OFF,
    CONF_POLLING_INTERVAL,
    MIN_POLLING_INTERVAL,
    CONF_EFFECTIVE_READ_TIMEOUT,
    MIN_EFFECTIVE_READ_TIMEOUT,
    DEFAULT_LANGUAGE,
)
from pandora_cas.account import PandoraOnlineAccount

_LOGGER = logging.getLogger(__name__)


def determine_method(entry: ConfigEntry | dict | None = None):
    if entry is None:
        return METHOD_COMBO
    if (entry.options or {}).get(CONF_DISABLE_WEBSOCKETS):
        if entry.pref_disable_polling:
            return METHOD_MANUAL
        return METHOD_POLL
    elif entry.pref_disable_polling:
        return METHOD_LISTEN
    return METHOD_COMBO


def determine_disabled(
    entry: ConfigEntry | str | None = None,
) -> tuple[bool, bool]:
    method = entry if isinstance(entry, str) else determine_method(entry)

    # (disable_websockets, disable_polling)
    return (
        method in (METHOD_MANUAL, METHOD_POLL),
        method in (METHOD_MANUAL, METHOD_LISTEN),
    )


STEP_USER: Final = "user"
STEP_USER_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


class PandoraCASConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pandora Car Alarm System config entries."""

    VERSION: Final[int] = 14

    def __init__(self) -> None:
        """Init the config flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            account = PandoraOnlineAccount(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                access_token=user_input.get(CONF_ACCESS_TOKEN),
                session=async_get_clientsession(
                    self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, True)
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

                # Handle new config entry
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Save access token for future reuse
                user_input[CONF_ACCESS_TOKEN] = account.access_token

                # Clear user input from data that is destined for options
                options = {CONF_VERIFY_SSL: user_input.pop(CONF_VERIFY_SSL, True)}

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                    options=options,
                )

            errors = {"base": error}
            schema = self.add_suggested_values_to_schema(
                ENTRY_DATA_SCHEMA,
                user_input,
            )
        elif entry := self._reauth_entry:
            errors = {"base": "invalid_auth"}
            schema = self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA,
                {
                    CONF_USERNAME: entry.data[CONF_USERNAME],
                    CONF_PASSWORD: "",
                    CONF_VERIFY_SSL: entry.options.get(CONF_VERIFY_SSL, True),
                },
            )
        else:
            errors = None
            schema = STEP_USER_SCHEMA

        return self.async_show_form(
            step_id=STEP_USER, data_schema=schema, errors=errors
        )

    # noinspection PyUnusedLocal
    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if (
            entry := self.hass.config_entries.async_get_entry(self.context["entry_id"])
        ).source == SOURCE_IMPORT:
            return self.async_abort(reason="yaml_not_supported")
        self._reauth_entry = entry
        return await self.async_step_user()

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
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
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        return PandoraCASOptionsFlow(config_entry)


STEP_SAVE: Final = "save"

DEFAULT_LANGUAGE_OPTIONS: Final = ("ru", "en", "it")

STEP_INTEGRATION_OPTIONS: Final = "integration_options"
STEP_INTEGRATION_OPTIONS_SCHEMA: Final = BASE_INTEGRATION_OPTIONS_SCHEMA.extend(
    {
        vol.Optional(CONF_METHOD, default=METHOD_COMBO): vol.In(
            {
                METHOD_COMBO: "WebSockets + HTTP",
                METHOD_POLL: "HTTP",
                METHOD_LISTEN: "WebSockets",
                METHOD_MANUAL: "Manual / Вручную",
            }
        )
    },
    extra=vol.REMOVE_EXTRA,
)

STEP_DEVICE_OPTIONS: Final = "device_options"


# STEP_DEVICE_OPTIONS_SCHEMA: Final = DEVICE_OPTIONS_SCHEMA


class PandoraCASOptionsFlow(OptionsFlowWithConfigEntry):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Helpers to handle the device_options step
        self.device_options: dict[str, str] | None = None
        self.current_pandora_id: str | None = None

        # Holders for current and edited options
        self.options[CONF_METHOD] = determine_method(self.config_entry)
        self.initial_options = deepcopy(self.options)
        self.device_options_schema: vol.Schema | None = None

    def _init_device_options(self):
        if self.device_options is None:
            self.device_options = {}
            dev_reg = device_registry.async_get(self.hass)
            for device in dev_reg.devices.values():
                for identifier in device.identifiers:
                    if len(identifier) != 2 or identifier[0] != DOMAIN:
                        continue
                    self.device_options[str(identifier[1])] = (
                        f"{device.name} ({identifier[1]})"
                    )

            for pandora_id in self.options.get(CONF_DEVICES) or {}:
                self.device_options.setdefault(
                    str(pandora_id), f"<unknown> ({pandora_id})"
                )

    # noinspection PyUnusedLocal
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        menu_options = [
            STEP_INTEGRATION_OPTIONS,
            STEP_DEVICE_OPTIONS,
        ]
        if dumps(self.options) != dumps(self.initial_options):
            menu_options.append(STEP_SAVE)
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    # noinspection PyUnusedLocal
    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        (
            self.options[CONF_DISABLE_WEBSOCKETS],
            disable_polling,
        ) = determine_disabled(self.options.pop(CONF_METHOD))

        if disable_polling is not self.config_entry.pref_disable_polling:
            # When polling is set to a value different from previous,
            # update directly before finishing flow.
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
            self._init_device_options()
            return self.async_show_menu(
                step_id=STEP_DEVICE_OPTIONS,
                menu_options={
                    f"{STEP_DEVICE_OPTIONS}_{pandora_id}": name
                    for pandora_id, name in self.device_options.items()
                },
            )

        if self.device_options_schema is None:
            translations = await async_get_translations(
                self.hass, self.hass.config.language, "entity", {DOMAIN}
            )
            entity_types_options = {}
            for full_key in DEVICE_OPTIONS_SCHEMA.schema[
                CONF_IGNORE_UPDATES_ENGINE_OFF
            ].options:
                domain, _, key = full_key.partition("__")
                translation_path = f"component.{DOMAIN}.entity.{domain}.{key}.name"
                entity_name = f"{domain}: {translations.get(translation_path) or key}"
                entity_types_options[full_key] = entity_name
            self.device_options_schema = DEVICE_OPTIONS_SCHEMA.extend(
                {
                    vol.Optional(
                        CONF_IGNORE_UPDATES_ENGINE_OFF, default=list
                    ): cv.multi_select(entity_types_options)
                }
            )

        schema = self.device_options_schema

        if user_input is None:
            # This value must already be set by the __setattr__ magic method
            if self.current_pandora_id is None:
                return self.async_abort("unknown")
            schema = self.add_suggested_values_to_schema(
                schema, self.options.get(CONF_DEVICES, {}).get(pandora_id, {})
            )
        else:
            self.options.setdefault(CONF_DEVICES, {}).setdefault(pandora_id, {}).update(
                user_input
            )
            self.current_pandora_id = None
            return await self.async_step_init()

        return self.async_show_form(step_id=STEP_DEVICE_OPTIONS, data_schema=schema)

    async def async_step_integration_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}

        if user_input is None:
            user_input = dict(self.options)
        else:
            # Check intervals
            for key, min_value in {
                CONF_POLLING_INTERVAL: MIN_POLLING_INTERVAL,
                CONF_EFFECTIVE_READ_TIMEOUT: MIN_EFFECTIVE_READ_TIMEOUT,
            }.items():
                if user_input[key] < min_value:
                    errors[key] = "interval_too_short"

            if not errors:
                self.options.update(user_input)
                return await self.async_step_init()

        schema = STEP_INTEGRATION_OPTIONS_SCHEMA
        if user_input.get(CONF_LANGUAGE) in DEFAULT_LANGUAGE_OPTIONS:
            schema = schema.extend(
                {
                    vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(
                        {
                            "ru": "Русский (ru)",
                            "en": "English (en)",
                            "it": "Italiano (it)",
                        }
                    )
                }
            )

        return self.async_show_form(
            step_id=STEP_INTEGRATION_OPTIONS,
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    def __getattr__(self, attribute):
        if isinstance(attribute, str) and attribute.startswith("async_step_device_"):
            pandora_id = attribute[18:]
            target_method = None
            if pandora_id.startswith("options_"):
                target_method = self.async_step_device_options
                pandora_id = pandora_id[8:]
            if target_method is not None and pandora_id.isnumeric():
                self.current_pandora_id = pandora_id
                return target_method
        raise AttributeError
