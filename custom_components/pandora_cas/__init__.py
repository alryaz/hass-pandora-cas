"""Initialization script for Pandora Car Alarm System component."""

__all__ = [
    'async_setup',
    'async_setup_entry',
    'async_unload_entry',
    'async_platform_setup_entry',
    'BasePandoraCASEntity',
    'PandoraCASEntity',
    'PandoraCASBooleanEntity',
    'CONFIG_SCHEMA',
    'SERVICE_REMOTE_COMMAND',
]

import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import Dict, Union, Optional, Any, Tuple, List, Type

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, ATTR_NAME, ATTR_DEVICE_CLASS, ATTR_ICON,
                                 ATTR_UNIT_OF_MEASUREMENT, ATTR_COMMAND)
from homeassistant.core import ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval, async_track_point_in_time
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import slugify, utcnow

from .api import (
    PandoraOnlineAccount,
    PandoraOnlineDevice,
    PandoraOnlineException,
    AuthenticationException,
    CommandID,
    DEFAULT_USER_AGENT
)

DOMAIN = 'pandora_cas'
PANDORA_COMPONENTS = ['binary_sensor', 'sensor', 'switch', 'lock', 'device_tracker']

DATA_CONFIG = DOMAIN + '_config'
DATA_UPDATERS = DOMAIN + '_updaters'
DATA_DEVICE_ENTITIES = DOMAIN + '_device_entities'

CONF_POLLING_INTERVAL = 'polling_interval'
CONF_READ_ONLY = 'read_only'
CONF_USER_AGENT = 'user_agent'
CONF_NAME_FORMAT = 'name_format'

ATTR_DEVICE_ID = 'device_id'
ATTR_COMMAND_ID = 'command_id'
ATTR_ATTRIBUTE = "attribute"
ATTR_FLAG = "flag"
ATTR_STATE_SENSITIVE = "state_sensitive"
ATTR_FORMATTER = "formatter"
ATTR_INVERSE = "inverse"
ATTR_FEATURE = "feature"
ATTR_ADDITIONAL_ATTRIBUTES = "additional_attributes"
ATTR_DEFAULT = "default"

DEFAULT_NAME_FORMAT = "{device_name} {type_name}"
MIN_POLLING_INTERVAL = timedelta(seconds=10)
DEFAULT_POLLING_INTERVAL = timedelta(minutes=1)
DEFAULT_EXECUTION_DELAY = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

_PLATFORM_OPTION_SCHEMA = vol.Any(cv.boolean, vol.All(cv.ensure_list, [cv.string]))
_DEVICE_INDEX_SCHEMA = vol.Any(vol.Equal(ATTR_DEFAULT), cv.string)
_PLATFORM_CONFIG_SCHEMA = vol.Any(
    vol.All(_PLATFORM_OPTION_SCHEMA, lambda x: {ATTR_DEFAULT: x}),
    {_DEVICE_INDEX_SCHEMA: _PLATFORM_OPTION_SCHEMA}
)

PANDORA_ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_USER_AGENT): cv.string,
    vol.Optional(CONF_NAME_FORMAT, default=DEFAULT_NAME_FORMAT): cv.string,
    vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL):
        vol.All(cv.time_period, vol.Clamp(min=MIN_POLLING_INTERVAL)),

    # Exemption: device_tracker (hardwired single entity in this context)
    vol.Optional('device_tracker'): vol.Any(
        vol.All(cv.boolean, lambda x: {ATTR_DEFAULT: x}),
        {_DEVICE_INDEX_SCHEMA: cv.boolean}
    )
}).extend({
    vol.Optional(platform_id): _PLATFORM_CONFIG_SCHEMA
    for platform_id in PANDORA_COMPONENTS
    if platform_id != 'device_tracker'
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        cv.ensure_list,
        [PANDORA_ACCOUNT_SCHEMA]
    ),
}, extra=vol.ALLOW_EXTRA)

SERVICE_REMOTE_COMMAND_PREDEFINED_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_ID): cv.string,
})

SERVICE_REMOTE_COMMAND = 'remote_command'
SERVICE_REMOTE_COMMAND_SCHEMA = SERVICE_REMOTE_COMMAND_PREDEFINED_SCHEMA.extend({
    vol.Required(ATTR_COMMAND_ID): vol.Coerce(int),
})

SERVICE_UPDATE_STATE = 'update_state'
_identifier_group = 'identifier_group'
UPDATE_SERVICE_SCHEMA = vol.Schema({
    vol.Exclusive(ATTR_DEVICE_ID, _identifier_group): cv.string,
    vol.Exclusive(CONF_USERNAME, _identifier_group): cv.string,
})


@callback
@bind_hass
def _find_existing_entry(hass: HomeAssistantType, username: str) -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if config_entry.data[CONF_USERNAME] == username:
            return config_entry


@bind_hass
async def _async_register_services(hass: HomeAssistantType) -> None:
    async def _execute_remote_command(call: 'ServiceCall', command_id: Optional[Union[int, CommandID]] = None) -> bool:
        _LOGGER.debug('Called service "%s" with data: %s' % (call.service, dict(call.data)))
        device_id = call.data[ATTR_DEVICE_ID]
        for username, account in hass.data[DOMAIN].items():
            account: PandoraOnlineAccount
            device_object = account.get_device(device_id)
            if device_object is not None:
                if command_id is None:
                    command_id = call.data[ATTR_COMMAND_ID]

                result = device_object.async_remote_command(command_id, ensure_complete=False)
                if asyncio.iscoroutine(result):
                    await result

                return True
        _LOGGER.error('Device with ID "%s" not found' % (device_id,))
        return False

    # register the remote services
    _register_service = hass.services.async_register

    _register_service(DOMAIN, SERVICE_REMOTE_COMMAND,
                      _execute_remote_command,
                      schema=SERVICE_REMOTE_COMMAND_SCHEMA)

    for key, value in CommandID.__members__.items():
        _register_service(DOMAIN, slugify(key.lower()),
                          partial(_execute_remote_command, command_id=value.value),
                          schema=SERVICE_REMOTE_COMMAND_SCHEMA)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Activate Pandora Car Alarm System component"""

    # Account holder
    hass.data[DOMAIN] = dict()

    # Updater holder
    hass.data[DATA_UPDATERS] = dict()

    # Enabled entities holder
    hass.data[DATA_DEVICE_ENTITIES] = dict()

    # YAML configuration holder
    data_config: Dict[str, Dict[str, Any]] = dict()
    hass.data[DATA_CONFIG] = data_config

    # Register services
    hass.async_create_task(_async_register_services(hass))

    # YAML configuration loader
    domain_config = config.get(DOMAIN)
    if domain_config:
        for account_cfg in domain_config:
            username = account_cfg.get(CONF_USERNAME)
            log_suffix = (username,)

            _LOGGER.debug('Account "%s" entry from YAML' % log_suffix)

            existing_entry = _find_existing_entry(hass, username)
            if existing_entry:
                if existing_entry.source == config_entries.SOURCE_IMPORT:
                    data_config[username] = account_cfg
                    _LOGGER.debug('Skipping existing import binding for account "%s"' % log_suffix)
                else:
                    _LOGGER.warning('YAML config for account "%s" is overridden by another config entry!' % log_suffix)
                continue

            if username in data_config:
                _LOGGER.warning('Account "%s" set up multiple times. Check your configuration.' % log_suffix)
                continue

            _LOGGER.debug('Adding account "%s" entry' % log_suffix)

            data_config[username] = account_cfg
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={CONF_USERNAME: username},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Setup configuration entry for Pandora Car Alarm System."""
    pandora_cfg = config_entry.data
    username = pandora_cfg[CONF_USERNAME]

    _LOGGER.debug('Setting up entry "%s" for account "%s"' % (config_entry.entry_id, username))

    if config_entry.source == config_entries.SOURCE_IMPORT:
        pandora_cfg = hass.data[DATA_CONFIG].get(username)
        if not pandora_cfg:
            _LOGGER.info('Removing entry %s after removal from YAML configuration.' % config_entry.entry_id)
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
            return False

    else:
        pandora_cfg = PANDORA_ACCOUNT_SCHEMA(dict(pandora_cfg))

    # create account object
    account = PandoraOnlineAccount(
        username, pandora_cfg[CONF_PASSWORD],
        user_agent=pandora_cfg.get(CONF_USER_AGENT, DEFAULT_USER_AGENT)
    )

    async def _authenticate():
        try:
            _LOGGER.debug('Authenticating account "%s"' % (username,))
            await account.async_authenticate()

        except AuthenticationException as e:
            _LOGGER.error("Authentication error: %s" % (e,))
            raise ConfigEntryNotReady from None

        except PandoraOnlineException as e:
            _LOGGER.debug("API error: %s" % (e,))
            raise ConfigEntryNotReady from None

    await _authenticate()

    _LOGGER.debug('Fetching devices for account "%s"' % (username,))
    await account.async_update_vehicles()

    # save account to global
    hass.data[DOMAIN][username] = account

    # create account updater
    async def _account_changes_updater(*_):
        try:
            _LOGGER.debug('Fetching changes for account "%s"' % (username,))
            _, updated_device_ids = await account.async_fetch_changes()

        except PandoraOnlineException:
            # Attempt to reauthenticate should an issue arise
            await _authenticate()
            _, updated_device_ids = await account.async_fetch_changes()

        # Iterate over updated device IDs
        for device_id in updated_device_ids:

            # Schedule entity updates for related entities
            device_entities: Optional[List[PandoraCASEntity]] = hass.data[DATA_DEVICE_ENTITIES].get(device_id)
            if device_entities is None:
                _LOGGER.debug('Received update for device "%s" without registration'
                              % (device_id,))
                continue

            elif not device_entities:
                # Do not iterate when there are no entities
                _LOGGER.debug('Received update for device with ID "%s" with no entities'
                              % (device_id,))
                continue

            _updated_entity_ids = list()
            for entity in device_entities:
                if entity.enabled:
                    _updated_entity_ids.append(entity.entity_id)
                    entity.async_schedule_update_ha_state(force_refresh=True)

            _LOGGER.debug('Scheduling update for device with ID "%s" for entities: %s'
                          % (device_id, ', '.join(_updated_entity_ids)))

    async def _start_updater(delay: Union[float, int, timedelta] = 0):
        if not isinstance(delay, timedelta):
            # Convert integers and floats to timedelta objects
            delay = timedelta(seconds=delay)

        # Check whether delay is required
        if delay.total_seconds():
            # Schedule updater to start with a `start_after` delay
            call_at = utcnow() + delay
            _LOGGER.debug('Scheduling updater for account "%s" at %s' % (username, call_at,))

            def _internal_start_updater(*_):
                _LOGGER.debug('Executing scheduled updater initialization for account "%s"' % (username,))
                hass.async_run_job(_start_updater)

            _cancel_updater = async_track_point_in_time(hass, _internal_start_updater, call_at)

        else:
            try:
                # Run updater once before establishing schedule
                await _account_changes_updater()

            except PandoraOnlineException:
                _LOGGER.exception('Error occurred while running updater:')

            # Schedule updater to run with configured polling interval
            _cancel_updater = async_track_time_interval(
                hass=hass,
                action=_account_changes_updater,
                interval=pandora_cfg[CONF_POLLING_INTERVAL]
            )

        if username in hass.data[DATA_UPDATERS]:
            # Cancel previous updater schedule
            hass.data[DATA_UPDATERS][username][1]()

        hass.data[DATA_UPDATERS][username] = (_start_updater, _cancel_updater)

    # Update stats once, and schedule the updater
    await _start_updater()

    # forward sub-entity setup
    for entity_domain in PANDORA_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry,
                entity_domain
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Unload configuration entry."""
    username = config_entry.data[CONF_USERNAME]

    if username in hass.data[DATA_UPDATERS]:
        _, cancel_updater = hass.data[DATA_UPDATERS].pop(username)
        cancel_updater()

    if username in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(username)

    # Wait for platforms to unload
    await asyncio.wait([
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(
                config_entry,
                platform_id
            ),
        )
        for platform_id in PANDORA_COMPONENTS
    ], return_when=asyncio.ALL_COMPLETED)

    return True


async def async_platform_setup_entry(platform_id: str,
                                     entity_class: Type['PandoraCASEntity'],
                                     hass: HomeAssistantType,
                                     config_entry: ConfigEntry,
                                     async_add_entities,
                                     logger: logging.Logger = _LOGGER):
    """Generic platform setup function"""
    logger.debug('Setting up platform "%s" with entity class "%s"' % (platform_id, entity_class.__name__))

    account_cfg = config_entry.data
    username = account_cfg[CONF_USERNAME]

    if config_entry.source == config_entries.SOURCE_IMPORT:
        account_cfg = hass.data[DATA_CONFIG][username]

    account_object: PandoraOnlineAccount = hass.data[DOMAIN][username]

    logger.debug('Account object for account "%s": %r' % (username, account_object))

    new_entities = []
    for device in account_object.devices:
        device_id = device.device_id

        logger.debug('Setting up device "%s" for platform "%s"' % (device_id, platform_id))

        entity_configs = entity_class.ENTITY_TYPES

        # Parse platform filtering directives
        device_directive: Optional[Union[bool, List[str]]]
        platform_directive = account_cfg.get(platform_id)
        if platform_directive is None:
            # Use default strategy when no directives are set up
            device_directive = None
        elif isinstance(platform_directive, bool):
            # (deprecated) Use root-level filtering
            device_directive = platform_directive
        else:
            device_directive = platform_directive.get(str(device_id))
            if device_directive is None:
                device_directive = platform_directive.get(ATTR_DEFAULT)

        # Apply filters
        if device_directive is None:
            enabled_entity_types = [
                sensor_type
                for sensor_type, sensor_config in entity_configs.items()
                if sensor_config.get(ATTR_DEFAULT, False)
            ]
            logger.debug('Using default objects for device "%s" during platform "%s" setup' % (device_id, platform_id))
        elif device_directive is True:
            enabled_entity_types = entity_configs.keys()
            logger.debug('Adding all objects to device "%s" during platform "%s" setup' % (device_id, platform_id))
        elif device_directive is False:
            logger.debug('Skipping device "%s" during platform "%s" setup' % (device_id, platform_id))
            continue
        else:
            enabled_entity_types = entity_configs.keys() & device_directive
            logger.debug('Filtering device "%s" during platform "%s" setup' % (device_id, platform_id))

        for entity_type, entity_config in entity_configs.items():
            if ATTR_FEATURE in entity_config and not entity_config[ATTR_FEATURE] & device.features:
                logger.debug('Entity "%s" disabled because end device "%s" does not support it'
                             % (entity_type, device_id))
                continue

            new_entities.append(entity_class(
                device=device,
                entity_type=entity_type,
                default_enable=entity_type in enabled_entity_types,
                name_format=account_cfg.get(CONF_NAME_FORMAT, DEFAULT_NAME_FORMAT),
            ))

    if new_entities:
        async_add_entities(new_entities, True)
        logger.debug('Added new "%s" entities for account "%s": %s' % (platform_id, username, new_entities))
    else:
        logger.debug('Did not add new "%s" entities for account "%s"' % (platform_id, username))

    return True


class BasePandoraCASEntity(Entity):
    def __init__(self, device: 'PandoraOnlineDevice', entity_type: str, default_enable: bool = True,
                 name_format: str = DEFAULT_NAME_FORMAT):
        self._device = device
        self._entity_type = entity_type
        self._default_enable = default_enable
        self._name_format = name_format

        self._available = False

    @property
    def _entity_name_vars(self) -> Dict[str, str]:
        """Return entity type name"""
        return {'type': self._entity_type,
                'device_name': self._device.name,
                'device_id': self._device.device_id}

    @property
    def name(self) -> str:
        """Return default device name."""
        return self._name_format.format(**self._entity_name_vars)

    @property
    def available(self) -> bool:
        """Whether entity is currently available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return unique ID based on entity type."""
        return '%s_%s_%s' % (DOMAIN, self._device.device_id, self._entity_type)

    @property
    def should_poll(self) -> bool:
        """Do not poll entities (handled by central account updaters)."""
        return False

    async def async_added_to_hass(self):
        """Add entity to update scheduling."""
        device_id = self._device.device_id
        entities: List['BasePandoraCASEntity'] = \
            self.hass.data[DATA_DEVICE_ENTITIES].setdefault(device_id, list())

        entities.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Remove entity from update scheduling."""
        device_id = self._device.device_id
        entities: Optional[List['BasePandoraCASEntity']] = \
            self.hass.data[DATA_DEVICE_ENTITIES].get(device_id)

        if entities and self in entities:
            entities.remove(self)

    @property
    def device_info(self) -> Dict[str, Any]:
        """Unified device info dictionary."""
        return {
            "identifiers": {
                (DOMAIN, self._device.device_id),
            },
            "name": self._device.name,
            "manufacturer": "Pandora",
            "model": self._device.model,
            "sw_version": self._device.firmware_version + ' / ' + self._device.voice_version,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of an entity."""
        return {
            ATTR_DEVICE_ID: self._device.device_id,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable default sensors."""
        return self._default_enable


class PandoraCASEntity(BasePandoraCASEntity):
    ENTITY_TYPES: Dict[str, Dict[str, Any]] = NotImplemented
    ENTITY_ID_FORMAT: str = NotImplemented

    def __init__(self, device: 'PandoraOnlineDevice', entity_type: str, default_enable: bool = True,
                 name_format: str = DEFAULT_NAME_FORMAT):
        super().__init__(device, entity_type, default_enable, name_format)

        self._state = None
        self.entity_id = self.ENTITY_ID_FORMAT.format(slugify(str(device.device_id)) + '_' + slugify(entity_type))

    # Core functionality
    @property
    def _entity_config(self) -> Dict[str, Any]:
        return self.ENTITY_TYPES[self._entity_type]

    async def async_update(self):
        """Update entity from upstream device data."""
        if self._entity_config.get(ATTR_STATE_SENSITIVE) and not self._device.is_online:
            self._available = False
            self._state = None
            _LOGGER.debug('Entity unavailable: %s' % (self,))
            return

        attribute = self._entity_config[ATTR_ATTRIBUTE]

        try:
            value = getattr(self._device, attribute)
            formatter = self._entity_config.get(ATTR_FORMATTER)
            self._state = formatter(value) if formatter else value
            self._available = True

        except AttributeError:
            _LOGGER.error('Attribute error occurred on device "%s" with attribute "%s"'
                          % (self._device.device_id, attribute))
            self._available = False

    async def _run_device_command(self, command: Union[str, int, CommandID], schedule_update: bool = True):
        device_object = self._device
        if isinstance(command, str):
            command = getattr(device_object, command)
            if asyncio.iscoroutinefunction(command):
                result = command()
            else:
                result = self.hass.async_add_executor_job(command)
        else:
            result = device_object.async_remote_command(command, ensure_complete=False)

        await result

        if schedule_update:
            username = device_object.account.username
            if username in self.hass.data[DATA_UPDATERS]:
                await self.hass.data[DATA_UPDATERS][username][0](DEFAULT_EXECUTION_DELAY)
            else:
                _LOGGER.warning('Could not schedule updater for account "%s" after running command for device "%s"'
                                % (username, device_object.device_id))

    # Predefined properties from configuration set
    @property
    def _entity_name_vars(self) -> Dict[str, str]:
        """Return entity name variables"""
        return {**super()._entity_name_vars,
                'type_name': self._entity_config[ATTR_NAME]}

    @property
    def device_class(self) -> Optional[str]:
        """Return device class (if available)."""
        return self._entity_config.get(ATTR_DEVICE_CLASS)

    @property
    def icon(self) -> Optional[str]:
        """Return device icon (if available)."""
        icon = self._entity_config.get(ATTR_ICON)
        if isinstance(icon, dict):
            return icon.get(self._state, icon[ATTR_DEFAULT])
        return icon

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._entity_config.get(ATTR_UNIT_OF_MEASUREMENT)


class PandoraCASBooleanEntity(PandoraCASEntity):
    @property
    def icon(self) -> Optional[str]:
        """Return the icon of the binary sensor."""
        icon: Optional[Union[str, Tuple[str, str]]] = super().icon

        if icon is not None:
            if isinstance(icon, str):
                return icon
            return icon[int(bool(self._state))]

    async def _run_boolean_command(self, enable: bool, shallow_update: bool = True):
        command = self._entity_config[ATTR_COMMAND]

        if isinstance(command, str):
            raise NotImplementedError
        else:
            await self._run_device_command(command[int(enable)])

        self._state = enable

        if shallow_update:
            self.async_schedule_update_ha_state(False)

    async def async_update(self):
        """Update entity from upstream device data."""
        config = self._entity_config
        if config.get(ATTR_STATE_SENSITIVE) and not self._device.is_online:
            self._available = False
            self._state = None
            _LOGGER.debug('Entity unavailable: %s' % (self,))
            return

        if not self.assumed_state:
            value = getattr(self._device, config[ATTR_ATTRIBUTE])
            if ATTR_FLAG in config:
                value &= config[ATTR_FLAG]

            self._state = bool(value) ^ self._entity_config.get(ATTR_INVERSE, False)

        self._available = True
