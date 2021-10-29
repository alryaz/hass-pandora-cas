"""Initialization script for Pandora Car Alarm System component."""

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "async_migrate_entry",
    "async_platform_setup_entry",
    "BasePandoraCASEntity",
    "PandoraCASEntity",
    "PandoraCASBooleanEntity",
    "CONFIG_SCHEMA",
    "SERVICE_REMOTE_COMMAND",
]

import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass
from homeassistant.util import slugify

from .api import (
    AuthenticationException,
    CommandID,
    CurrentState,
    DEFAULT_USER_AGENT,
    PandoraOnlineAccount,
    PandoraOnlineDevice,
    PandoraOnlineException,
    TrackingEvent,
    TrackingPoint,
)
from .const import *

MIN_POLLING_INTERVAL = timedelta(seconds=10)
DEFAULT_POLLING_INTERVAL = timedelta(minutes=1)
DEFAULT_EXECUTION_DELAY = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

_PLATFORM_OPTION_SCHEMA = vol.Any(cv.boolean, vol.All(cv.ensure_list, [cv.string]))
_DEVICE_INDEX_SCHEMA = vol.Any(vol.Equal(ATTR_DEFAULT), cv.string)
_PLATFORM_CONFIG_SCHEMA = vol.Any(
    vol.All(_PLATFORM_OPTION_SCHEMA, lambda x: {ATTR_DEFAULT: x}),
    {_DEVICE_INDEX_SCHEMA: _PLATFORM_OPTION_SCHEMA},
)

_PLATFORM_TYPES_VALIDATOR = vol.Any(
    cv.boolean, vol.All(cv.ensure_list, [cv.string], vol.Coerce(set), vol.Coerce(list))
)


def _get_validator(validator, default_value):
    return vol.Any(
        vol.All(validator, lambda x: {ATTR_DEFAULT: x}),
        {
            vol.Optional(ATTR_DEFAULT, default=default_value): validator,
            cv.string: validator,
        },
    )


PANDORA_ACCOUNT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_NAME_FORMAT, default=DEFAULT_NAME_FORMAT): cv.string,
            # Exemption: device_tracker (hardwired single entity in this context)
            vol.Optional("device_tracker", default=True): vol.Any(
                vol.All(cv.boolean, lambda x: {ATTR_DEFAULT: x}),
                vol.All(
                    cv.ensure_list,
                    [cv.string],
                    lambda x: {ATTR_DEFAULT: False, **dict.fromkeys(x, True)},
                ),
                vol.All(cv.boolean, lambda x: {ATTR_DEFAULT: x}),
            ),
            vol.Optional(
                CONF_RPM_COEFFICIENT, default=DEFAULT_RPM_COEFFICIENT
            ): _get_validator(cv.positive_float, DEFAULT_RPM_COEFFICIENT),
            vol.Optional(CONF_RPM_OFFSET, default=DEFAULT_RPM_OFFSET): _get_validator(
                cv.positive_float, DEFAULT_RPM_OFFSET
            ),
        }
    ).extend(
        {
            vol.Optional(platform_id, default=True): _get_validator(
                _PLATFORM_TYPES_VALIDATOR, True
            )
            for platform_id in PANDORA_COMPONENTS
            if platform_id != "device_tracker"
        }
    ),
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(cv.ensure_list, [PANDORA_ACCOUNT_SCHEMA]),
    },
    extra=vol.ALLOW_EXTRA,
)


def _determine_command_by_slug(command_slug: str) -> int:
    enum_member = command_slug.upper().strip()
    for key, value in CommandID.__members__.items():
        if key == enum_member:
            return value

    raise vol.Invalid("invalid command identifier")


SERVICE_REMOTE_COMMAND = "remote_command"
SERVICE_REMOTE_COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_DEVICE_ID, "device_id"): cv.string,
            vol.Exclusive(ATTR_ID, "device_id"): cv.string,
            vol.Required(ATTR_COMMAND_ID): vol.Any(
                cv.positive_int,
                vol.All(cv.string, _determine_command_by_slug),
            ),
        }
    ),
    cv.deprecated(ATTR_ID, ATTR_DEVICE_ID),
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

SERVICE_PREDEFINED_COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_DEVICE_ID, "device_id"): cv.string,
            vol.Exclusive(ATTR_ID, "device_id"): cv.string,
        }
    ),
    cv.deprecated(ATTR_ID, ATTR_DEVICE_ID),
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

SERVICE_UPDATE_STATE = "update_state"
_identifier_group = "identifier_group"
UPDATE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_DEVICE_ID, _identifier_group): cv.string,
        vol.Exclusive(CONF_USERNAME, _identifier_group): cv.string,
    }
)


@callback
@bind_hass
def _find_existing_entry(
    hass: HomeAssistantType, username: str
) -> Optional[config_entries.ConfigEntry]:
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for config_entry in existing_entries:
        if config_entry.data[CONF_USERNAME] == username:
            return config_entry


@bind_hass
async def _async_register_services(hass: HomeAssistantType) -> None:
    async def _execute_remote_command(
        call: "ServiceCall", command_id: Optional[Union[int, CommandID]] = None
    ) -> None:
        _LOGGER.debug(f"Called service '{call.service}' with data: {dict(call.data)}")

        device_id = call.data[ATTR_DEVICE_ID]
        for username, account in hass.data[DOMAIN].items():
            account: PandoraOnlineAccount
            device_object = account.get_device(device_id)
            if device_object is not None:
                if command_id is None:
                    command_id = call.data[ATTR_COMMAND_ID]

                result = device_object.async_remote_command(
                    command_id, ensure_complete=False
                )
                if asyncio.iscoroutine(result):
                    await result

                return

        raise ValueError(f"Device with ID '{device_id}' not found")

    # register the remote services
    _register_service = hass.services.async_register

    _register_service(
        DOMAIN,
        SERVICE_REMOTE_COMMAND,
        _execute_remote_command,
        schema=SERVICE_REMOTE_COMMAND_SCHEMA,
    )

    for key, value in CommandID.__members__.items():
        command_slug = slugify(key.lower())
        _LOGGER.debug(
            f"Registered remote command: {command_slug} (command_id={value.value})"
        )
        _register_service(
            DOMAIN,
            command_slug,
            partial(
                _execute_remote_command,
                command_id=value.value,
            ),
            schema=SERVICE_PREDEFINED_COMMAND_SCHEMA,
        )


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
                    _LOGGER.debug(
                        'Skipping existing import binding for account "%s"' % log_suffix
                    )
                else:
                    _LOGGER.warning(
                        'YAML config for account "%s" is overridden by another config entry!'
                        % log_suffix
                    )
                continue

            if username in data_config:
                _LOGGER.warning(
                    'Account "%s" set up multiple times. Check your configuration.'
                    % log_suffix
                )
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

    _LOGGER.debug(
        'Setting up entry "%s" for account "%s"' % (config_entry.entry_id, username)
    )

    if config_entry.source == config_entries.SOURCE_IMPORT:
        pandora_cfg = hass.data[DATA_CONFIG].get(username)
        if not pandora_cfg:
            _LOGGER.info(
                "Removing entry %s after removal from YAML configuration."
                % config_entry.entry_id
            )
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
            return False

    else:
        pandora_cfg = PANDORA_ACCOUNT_SCHEMA({**pandora_cfg, **config_entry.options})

    # create account object
    account = PandoraOnlineAccount(
        username,
        pandora_cfg[CONF_PASSWORD],
    )

    try:
        _LOGGER.debug('Authenticating account "%s"' % (username,))
        await account.async_authenticate()

        _LOGGER.debug('Fetching devices for account "%s"' % (username,))
        await account.async_update_vehicles()

    except PandoraOnlineException as error:
        await account.async_close()

        _LOGGER.error(error)
        raise ConfigEntryNotReady(str(error)) from None

    # save account to global
    hass.data[DOMAIN][config_entry.entry_id] = account

    # create account updater
    async def _state_changes_listener(
        device: PandoraOnlineDevice, _: CurrentState, updated_stats: Mapping[str, Any]
    ):
        # Schedule entity updates for related entities
        device_id = device.device_id

        device_entities: Optional[List[PandoraCASEntity]] = hass.data[
            DATA_DEVICE_ENTITIES
        ].get(device_id)

        if device_entities is None:
            _LOGGER.debug(
                'Received update for device "%s" without entities' % (device_id,)
            )
            return

        if not device_entities:
            # Do not iterate when there are no entities
            _LOGGER.debug(
                'Received update for device with ID "%s" with no entities'
                % (device_id,)
            )
            return

        _updated_entity_ids = list()
        for entity in device_entities:
            if entity.enabled:
                if hasattr(entity, "entity_type_config"):
                    entity_type_config = entity.entity_type_config

                    if entity_type_config.get(ATTR_ATTRIBUTE_SOURCE) is None and not (
                            ATTR_ATTRIBUTE in entity_type_config
                            and entity_type_config[ATTR_ATTRIBUTE] in updated_stats
                    ):
                        continue

                _updated_entity_ids.append(entity.entity_id)
                entity.async_schedule_update_ha_state(force_refresh=True)

        _LOGGER.debug(
            f"Scheduling update for device with ID '{device_id}' "
            f"for entities: {', '.join(_updated_entity_ids)}"
        )

    async def _command_execution_listener(
        device: PandoraOnlineDevice,
        command_id: int,
        result: int,
        reply: Any,
    ):
        _LOGGER.debug(
            "Received command execution result: %s / %s / %s", command_id, result, reply
        )

        hass.bus.async_fire(
            f"{DOMAIN}_command",
            {
                "device_id": device.device_id,
                "command_id": command_id,
                "result": result,
                "reply": reply,
            },
        )

    async def _event_catcher_listener(
        device: PandoraOnlineDevice,
        event: TrackingEvent,
    ):
        _LOGGER.info("Received event: %s", event)

        hass.bus.async_fire(
            f"{DOMAIN}_event",
            {
                "device_id": device.device_id,
                "event_id_primary": event.event_id_primary,
                "event_id_secondary": event.event_id_secondary,
                "event_type": event.primary_event_enum.name.lower(),
                "latitude": event.latitude,
                "longitude": event.longitude,
                "gsm_level": event.gsm_level,
                "fuel": event.fuel,
                "exterior_temperature": event.exterior_temperature,
                "engine_temperature": event.engine_temperature,
            },
        )

    async def _point_catcher_listener(
        device: PandoraOnlineDevice,
        point: TrackingPoint,
    ):
        _LOGGER.info("Received point: %s", point)

        hass.bus.async_fire(
            f"{DOMAIN}_point",
            {
                "device_id": device.device_id,
                "timestamp": point.timestamp,
                "track_id": point.track_id,
                "fuel": point.fuel,
                "speed": point.speed,
                "max_speed": point.max_speed,
                "length": point.length,
            },
        )

    # Start listening for updates
    hass.data.setdefault(DATA_UPDATERS, {})[
        config_entry.entry_id
    ] = hass.loop.create_task(
        account.async_listen_for_updates(
            state_callback=_state_changes_listener,
            command_callback=_command_execution_listener,
            event_callback=_event_catcher_listener,
            point_callback=_point_catcher_listener,
        )
    )

    hass.data.setdefault(DATA_FINAL_CONFIG, {})[config_entry.entry_id] = pandora_cfg

    # forward sub-entity setup
    for entity_domain in PANDORA_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, entity_domain)
        )

    # Create options update listener
    update_listener = config_entry.add_update_listener(async_reload_entry)
    hass.data.setdefault(DATA_UPDATE_LISTENERS, {})[
        config_entry.entry_id
    ] = update_listener

    return True


async def async_reload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Reload Lkcomu InterRAO entry"""
    _LOGGER.info("Reloading configuration entry")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload configuration entry."""
    entry_id = config_entry.entry_id
    if entry_id in hass.data[DOMAIN]:
        account = hass.data[DOMAIN].pop(entry_id)
        await account.async_close()

    username = config_entry.data[CONF_USERNAME]

    if username in hass.data[DATA_UPDATERS]:
        listen_task: Optional[asyncio.Task] = hass.data[DATA_UPDATERS].pop(
            config_entry.entry_id
        )
        if listen_task and not listen_task.done():
            listen_task.cancel()

    # Wait for platforms to unload
    await asyncio.wait(
        [
            hass.async_create_task(
                hass.config_entries.async_forward_entry_unload(
                    config_entry, platform_id
                ),
            )
            for platform_id in PANDORA_COMPONENTS
        ],
        return_when=asyncio.ALL_COMPLETED,
    )

    update_listener = hass.data.get(DATA_UPDATE_LISTENERS, {}).pop(
        config_entry.entry_id, None
    )
    if callable(update_listener):
        update_listener()

    return True


async def async_migrate_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    _LOGGER.info(f"Upgrading configuration entry from version {config_entry.version}")

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}

    if config_entry.version < 2:
        for src in (new_data, new_options):
            for key in ("polling_interval", "user_agent"):
                if key in src:
                    del src[key]
        config_entry.version = 2

    hass.config_entries.async_update_entry(config_entry, data=new_data, options=new_options)

    _LOGGER.info(f"Upgraded configuration entry to version {config_entry.version}")

    return True



async def async_platform_setup_entry(
    platform_id: str,
    entity_class: Type["PandoraCASEntity"],
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities,
    logger: logging.Logger = _LOGGER,
):
    """Generic platform setup function"""
    logger.debug(
        'Setting up platform "%s" with entity class "%s"'
        % (platform_id, entity_class.__name__)
    )

    account_cfg = hass.data[DATA_FINAL_CONFIG][config_entry.entry_id]
    username = account_cfg[CONF_USERNAME]
    account_object: PandoraOnlineAccount = hass.data[DOMAIN][config_entry.entry_id]

    logger.debug('Account object for account "%s": %r' % (username, account_object))

    new_entities = []
    for device in account_object.devices:
        device_id = device.device_id

        logger.debug(
            'Setting up device "%s" for platform "%s"' % (device_id, platform_id)
        )

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
                if not sensor_config.get(ATTR_DISABLED_BY_DEFAULT, False)
            ]
            logger.debug(
                'Using default objects for device "%s" during platform "%s" setup'
                % (device_id, platform_id)
            )

        elif device_directive is True:
            enabled_entity_types = entity_configs.keys()
            logger.debug(
                'Adding all objects to device "%s" during platform "%s" setup'
                % (device_id, platform_id)
            )
        elif device_directive is False:
            logger.debug(
                'Skipping device "%s" during platform "%s" setup'
                % (device_id, platform_id)
            )
            continue
        else:
            enabled_entity_types = entity_configs.keys() & device_directive
            logger.debug(
                'Filtering device "%s" during platform "%s" setup'
                % (device_id, platform_id)
            )

        for entity_type, entity_config in entity_configs.items():
            if (
                    ATTR_FEATURE in entity_config
                    and not entity_config[ATTR_FEATURE] & device.features
            ):
                logger.debug(
                    'Entity "%s" disabled because end device "%s" does not support it'
                    % (entity_type, device_id)
                )
                continue

            new_entities.append(
                entity_class(
                    config_entry=config_entry,
                    account_cfg=account_cfg,
                    device=device,
                    entity_type=entity_type,
                    default_enable=entity_type in enabled_entity_types,
                )
            )

    if new_entities:
        async_add_entities(new_entities, True)
        logger.debug(
            'Added new "%s" entities for account "%s": %s'
            % (platform_id, username, new_entities)
        )
    else:
        logger.debug(
            'Did not add new "%s" entities for account "%s"' % (platform_id, username)
        )

    return True


class BasePandoraCASEntity(Entity):
    def __init__(
        self,
        config_entry: ConfigEntry,
        account_cfg: Mapping[str, Any],
        device: "PandoraOnlineDevice",
        entity_type: str,
        default_enable: bool = True,
    ) -> None:
        self._device = device
        self._entity_type = entity_type
        self._default_enable = default_enable
        self._account_cfg = account_cfg
        self._config_entry = config_entry

        self._available = False

    @property
    def _entity_name_vars(self) -> Dict[str, str]:
        """Return entity type name"""
        return {
            "type": self._entity_type,
            "device_name": self._device.name,
            "device_id": self._device.device_id,
        }

    @property
    def name(self) -> str:
        """Return default device name."""
        return (self._account_cfg.get(CONF_NAME_FORMAT) or DEFAULT_NAME_FORMAT).format(
            **self._entity_name_vars
        )

    @property
    def available(self) -> bool:
        """Whether entity is currently available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return unique ID based on entity type."""
        return "%s_%s_%s" % (DOMAIN, self._device.device_id, self._entity_type)

    @property
    def should_poll(self) -> bool:
        """Do not poll entities (handled by central account updaters)."""
        return False

    async def async_added_to_hass(self):
        """Add entity to update scheduling."""
        device_id = self._device.device_id
        entities: List["BasePandoraCASEntity"] = self.hass.data[
            DATA_DEVICE_ENTITIES
        ].setdefault(device_id, list())

        entities.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Remove entity from update scheduling."""
        device_id = self._device.device_id
        entities: Optional[List["BasePandoraCASEntity"]] = self.hass.data[
            DATA_DEVICE_ENTITIES
        ].get(device_id)

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
            "sw_version": (
                self._device.firmware_version
                + " / "
                + self._device.voice_version
            ),
        }

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of an entity."""
        return {
            ATTR_DEVICE_ID: self._device.device_id,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable default sensors."""
        return self._default_enable


class PandoraCASEntity(BasePandoraCASEntity):
    ENTITY_TYPES: ClassVar[Dict[str, Dict[str, Any]]] = NotImplemented
    ENTITY_ID_FORMAT: ClassVar[str] = NotImplemented

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._state = None
        self.entity_id = self.ENTITY_ID_FORMAT.format(
            slugify(str(self._device.device_id)) + "_" + slugify(self._entity_type)
        )

    # Core functionality
    @property
    def entity_type_config(self) -> Dict[str, Any]:
        return self.ENTITY_TYPES[self._entity_type]

    def _get_attribute_value(self) -> Optional[Any]:
        """Update entity from upstream device data."""
        entity_type_config = self.entity_type_config
        attribute_source_getter = entity_type_config.get(ATTR_ATTRIBUTE_SOURCE)
        if attribute_source_getter:
            if callable(attribute_source_getter):
                source = attribute_source_getter(self._device)
            else:
                source = self._device
        else:
            source = self._device.state

        if source is None:
            return None

        return getattr(source, entity_type_config[ATTR_ATTRIBUTE])

    async def async_update(self):
        """Update entity from upstream device data."""
        if (
                self.entity_type_config.get(ATTR_STATE_SENSITIVE)
                and not self._device.is_online
        ):
            self._available = False
            self._state = None
            _LOGGER.debug("Entity unavailable: %s" % (self,))
            return

        try:
            value = self._get_attribute_value()

        except AttributeError as e:
            _LOGGER.error(
                f"Attribute error occurred on device '{self._device.device_id}' "
                f"with attribute '{self.entity_type_config[ATTR_ATTRIBUTE]}': {e}"
            )
            self._available = False

        else:
            if value is None:
                self._available = False

            else:
                formatter = self.entity_type_config.get(ATTR_FORMATTER)
                self._state = formatter(value) if formatter else value
                self._available = True

    async def _run_device_command(self, command: Union[str, int, CommandID]):
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

    # Predefined properties from configuration set
    @property
    def _entity_name_vars(self) -> Dict[str, str]:
        """Return entity name variables"""
        return {
            **super()._entity_name_vars,
            "type_name": self.entity_type_config[ATTR_NAME],
        }

    @property
    def device_class(self) -> Optional[str]:
        """Return device class (if available)."""
        return self.entity_type_config.get(ATTR_DEVICE_CLASS)

    @property
    def state_class(self) -> Optional[str]:
        return self.entity_type_config.get(ATTR_STATE_CLASS)

    @property
    def icon(self) -> Optional[str]:
        """Return device icon (if available)."""
        icon = self.entity_type_config.get(ATTR_ICON)
        if isinstance(icon, dict):
            return icon.get(self._state, icon[ATTR_DEFAULT])
        return icon

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self.entity_type_config.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        attributes = super().device_state_attributes

        if ATTR_STATE_CLASS not in attributes:
            state_class = self.state_class
            if state_class is not None:
                attributes[ATTR_STATE_CLASS] = state_class

        return attributes


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
        command = self.entity_type_config[ATTR_COMMAND]

        if isinstance(command, str):
            raise NotImplementedError
        else:
            await self._run_device_command(command[int(enable)])

        self._state = enable

        if shallow_update:
            self.async_schedule_update_ha_state(False)

    async def async_update(self):
        """Update entity from upstream device data."""
        config = self.entity_type_config
        if config.get(ATTR_STATE_SENSITIVE) and not self._device.is_online:
            self._available = False
            self._state = None
            _LOGGER.debug("Entity unavailable: %s" % (self,))
            return

        if self.assumed_state:
            self._available = True

        else:
            try:
                value = self._get_attribute_value()

            except AttributeError as e:
                _LOGGER.error(
                    f"Attribute error occurred on device '{self._device.device_id}' "
                    f"with attribute '{self.entity_type_config[ATTR_ATTRIBUTE]}': {e}"
                )
                self._available = False

            else:
                if value is None:
                    self._available = False

                else:
                    if ATTR_FLAG in config:
                        value &= config[ATTR_FLAG]

                    self._state = bool(value) ^ self.entity_type_config.get(
                        ATTR_INVERSE, False
                    )

                    self._available = True
