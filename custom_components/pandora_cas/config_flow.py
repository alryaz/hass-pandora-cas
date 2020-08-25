"""Config flow for Pandora Car Alarm System component."""
__all__ = [
    'PandoraCASConfigFlow',
]
import logging
import voluptuous as vol
from typing import Optional

from homeassistant import config_entries
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, DEFAULT_POLLING_INTERVAL, CONF_POLLING_INTERVAL, CONF_USER_AGENT
from .api import PandoraOnlineAccount, PandoraOnlineException, AuthenticationException

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class PandoraCASConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Pandora Car Alarm System config entries."""

    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        self._user_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL.total_seconds()): int,
            vol.Optional(CONF_USER_AGENT): str,
        })

    async def _check_entry_exists(self, username: str):
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

    async def _create_entry(self, config: ConfigType):
        """
        Finalize flow and create account entry.
        :param config: Configuration for account
        :return: (internal) Entry creation command
        """
        _LOGGER.debug('Creating entry: %s' % config)

        username = config[CONF_USERNAME]

        if await self._check_entry_exists(username):
            _LOGGER.warning('Configuration for account "%s" already exists, not adding' % (username,))
            return self.async_abort(reason="account_already_exists")

        _LOGGER.debug('Account "%s" entry: %s' % (username, config))

        return self.async_create_entry(title=username, data=config)

    async def async_step_user(self, user_input: Optional[ConfigType] = None):
        @callback
        def _show_form(error: Optional[str] = None):
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema,
                errors={'base': error} if error else None,
            )

        if not user_input:
            return _show_form()

        account = PandoraOnlineAccount(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            user_agent=user_input.get(CONF_USER_AGENT)
        )

        try:
            await account.async_authenticate()
            await account.async_update_vehicles()
        except AuthenticationException:
            return _show_form('invalid_credentials')
        except PandoraOnlineException:
            return _show_form('api_error')

        return await self._create_entry(user_input)

    async def async_step_import(self, user_input: Optional[ConfigType] = None):
        if user_input is None:
            _LOGGER.error('Called import step without configuration')
            return self.async_abort("empty_configuration_import")

        # Finalize with entry creation
        return await self._create_entry({CONF_USERNAME: user_input[CONF_USERNAME]})
