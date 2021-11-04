"""Config flow for Pandora Car Alarm System component."""
__all__ = ("PandoraCASConfigFlow", "PandoraCASOptionsFlow")

import logging
from typing import Any, Dict, Final, List, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .api import AuthenticationException, PandoraOnlineAccount, PandoraOnlineException

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class PandoraCASConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Pandora Car Alarm System config entries."""

    CONNECTION_CLASS: Final[str] = config_entries.CONN_CLASS_CLOUD_POLL
    VERSION: Final[int] = 2

    def __init__(self) -> None:
        self._user_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def _check_entry_exists(self, username: str) -> bool:
        """
        Check whether entry for account with given username exists.
        :param username: Account username
        :return: Query result
        """
        current_entries = self._async_current_entries()

        for config_entry in current_entries:
            if config_entry.data[CONF_USERNAME] == username:
                return True

        return False

    async def _create_entry(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize flow and create account entry.
        :param config: Configuration for account
        :return: (internal) Entry creation command
        """
        username = config[CONF_USERNAME]

        if await self._check_entry_exists(username):
            _LOGGER.warning(
                f"Configuration for username '{username}' "
                f"already exists, not adding"
            )
            return self.async_abort(reason="account_already_exists")

        _LOGGER.debug(f"Creating entry for username {username}")

        return self.async_create_entry(title=username, data=config)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        @callback
        def _show_form(error: Optional[str] = None):
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema,
                errors={"base": error} if error else None,
            )

        if not user_input:
            return _show_form()

        account = PandoraOnlineAccount(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
        )

        try:
            await account.async_authenticate()
            await account.async_update_vehicles()
        except AuthenticationException:
            return _show_form("invalid_credentials")
        except PandoraOnlineException:
            return _show_form("api_error")

        return await self._create_entry(user_input)

    async def async_step_import(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if user_input is None:
            _LOGGER.error("Called import step without configuration")
            return self.async_abort("empty_configuration_import")

        # Finalize with entry creation
        return await self._create_entry({CONF_USERNAME: user_input[CONF_USERNAME]})

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PandoraCASOptionsFlow(config_entry)


class PandoraCASOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self.use_text_fields = False
        self.config_codes: Optional[Dict[str, List[str]]] = None

    async def async_generate_schema_dict(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[vol.Marker, Any]:
        config_entry = self.config_entry

        # @TODO: reserved for future use
        final_config = {**config_entry.data, **config_entry.options}
        if user_input:
            final_config.update(user_input)

        schema_dict = {
            vol.Optional(CONF_PASSWORD): str,
        }

        return schema_dict

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if self.config_entry.source == config_entries.SOURCE_IMPORT:
            return self.async_abort(reason="yaml_not_supported")

        errors = {}
        if user_input:
            new_password = user_input.get(CONF_PASSWORD)
            if new_password:
                _LOGGER.debug("Password is getting updated")
                config_entry = self.config_entry

                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data={
                        **config_entry.data,
                        CONF_PASSWORD: new_password,
                    },
                )

                # Setting data to None cancels double update
                return self.async_create_entry(title="", data=None)

            # Stub update
            return self.async_create_entry(title="", data=None)

        schema_dict = await self.async_generate_schema_dict(user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
