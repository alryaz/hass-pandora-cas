"""Config flow for Pandora Car Alarm System component."""
__all__ = ("PandoraCASConfigFlow",)

import logging
from typing import (
    Any,
    Dict,
    Final,
    Optional,
)

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_ACCESS_TOKEN,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers import config_validation, device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaOptionsFlowHandler,
    SchemaFlowFormStep,
    SchemaCommonFlowHandler,
)

from custom_components.pandora_cas import async_run_pandora_coro
from custom_components.pandora_cas.api import (
    PandoraOnlineAccount,
)
from custom_components.pandora_cas.const import (
    DOMAIN,
    CONF_OFFLINE_AS_UNAVAILABLE,
    CONF_FUEL_IS_LITERS,
    CONF_CUSTOM_CURSORS,
    CONF_CUSTOM_CURSOR_DEVICES,
    CONF_CUSTOM_CURSOR_TYPE,
    CONF_MILEAGE_MILES,
    CONF_MILEAGE_CAN_MILES,
    DEFAULT_CURSOR_TYPE,
    DISABLED_CURSOR_TYPE,
)
from custom_components.pandora_cas.tracker_images import IMAGE_REGISTRY

_LOGGER = logging.getLogger(__name__)

OPTIONS_BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_OFFLINE_AS_UNAVAILABLE, default=False): bool,
        
    }
)

CUSTOM_CURSOR_TYPES_VALIDATOR: Final = vol.In(
    tuple([DEFAULT_CURSOR_TYPE, DISABLED_CURSOR_TYPE] + sorted(IMAGE_REGISTRY.keys()))
)


async def async_options_flow_init_step_create_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    dev_reg = device_registry.async_get(handler.parent_handler.hass)
    device_options = {}
    for device in dev_reg.devices.values():
        for identifier in device.identifiers:
            if len(identifier) != 2 or identifier[0] != DOMAIN:
                continue
            device_options[identifier[1]] = f"{device.name} ({identifier[1]})"
    for pandora_id in (handler.options or {}).get(CONF_FUEL_IS_LITERS) or ():
        device_options.setdefault(pandora_id, f"<unknown> ({pandora_id})")

    custom_cursors = handler.options.get(CONF_CUSTOM_CURSORS) or {}
    extend_dict = {
        vol.Optional(CONF_FUEL_IS_LITERS): config_validation.multi_select(
            device_options
        ),
        vol.Optional(
            CONF_CUSTOM_CURSOR_TYPE, default=DEFAULT_CURSOR_TYPE
        ): CUSTOM_CURSOR_TYPES_VALIDATOR,
        vol.Optional(
            CONF_CUSTOM_CURSOR_DEVICES
        ): config_validation.multi_select(
            {
                k: (f"{v} — {custom_cursors[k]}" if k in custom_cursors else v)
                for k, v in device_options.items()
            }
        ),
        vol.Optional(CONF_MILEAGE_MILES): config_validation.multi_select(
            device_options
        ),
        vol.Optional(CONF_MILEAGE_CAN_MILES): config_validation.multi_select(
            device_options
        ),
    }

    return OPTIONS_BASE_SCHEMA.extend(extend_dict)


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


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        async_options_flow_init_step_create_schema,
        async_options_flow_init_step_validate,
    )
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class PandoraCASConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pandora Car Alarm System config entries."""

    CONNECTION_CLASS: Final[str] = config_entries.CONN_CLASS_CLOUD_PUSH
    VERSION: Final[int] = 7

    def __init__(self) -> None:
        """Init the config flow."""
        self._reauth_entry: Optional[config_entries.ConfigEntry] = None

    async def _create_entry(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize flow and create account entry.
        :param config: Configuration for account
        :return: (internal) Entry creation command
        """

        _LOGGER.debug(f"Creating entry for username {config[CONF_USERNAME]}")

        return self.async_create_entry(
            title=config[CONF_USERNAME],
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
            options={
                CONF_VERIFY_SSL: config[CONF_VERIFY_SSL],
            },
        )

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

                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCESS_TOKEN: account.access_token,
                        },
                        options={
                            CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                        },
                    )

            errors = {"base": error}
            schema = self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input,
            )
        elif entry := self._reauth_entry:
            errors = {"base": "invalid_auth"}
            schema = self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {**entry.data, **entry.options, CONF_PASSWORD: ""},
            )
        else:
            errors = None
            schema = STEP_USER_DATA_SCHEMA

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
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
