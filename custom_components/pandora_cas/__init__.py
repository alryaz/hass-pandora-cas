"""Initialization script for Pandora Car Alarm System component."""

__all__ = (
    "BASE_INTEGRATION_OPTIONS_SCHEMA",
    "CONFIG_ENTRY_SCHEMA",
    "CONFIG_SCHEMA",
    "ConfigEntryLoggerAdapter",
    "DEVICE_OPTIONS_SCHEMA",
    "ENTRY_DATA_SCHEMA",
    "ENTRY_OPTIONS_SCHEMA",
    "INTEGRATION_OPTIONS_SCHEMA",
    "PandoraCASUpdateCoordinator",
    "SERVICE_PREDEFINED_COMMAND_SCHEMA",
    "SERVICE_REMOTE_COMMAND",
    "SERVICE_REMOTE_COMMAND_SCHEMA",
    "async_migrate_entry",
    "async_run_pandora_coro",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "event_enum_to_type",
)

import asyncio
import importlib
import logging
from datetime import timedelta, datetime
from functools import partial
from json import JSONDecodeError
from time import time
from typing import (
    Any,
    Mapping,
    Type,
    TypeVar,
    Awaitable,
    Literal,
    MutableMapping,
)

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    SOURCE_IMPORT,
    current_entry,
)
from homeassistant.const import (
    ATTR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_ACCESS_TOKEN,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICES,
    CONF_LANGUAGE,
    ATTR_DEVICE_ID,
)
from homeassistant.core import ServiceCall, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
    async_entries_for_config_entry,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.loader import bind_hass
from homeassistant.util import slugify

from custom_components.pandora_cas.const import *
from custom_components.pandora_cas.tracker_images import IMAGE_REGISTRY
from pandora_cas.account import PandoraOnlineAccount
from pandora_cas.data import CurrentState, TrackingEvent, TrackingPoint
from pandora_cas.device import PandoraOnlineDevice
from pandora_cas.enums import CommandID, PrimaryEventID
from pandora_cas.errors import AuthenticationError, MalformedResponseError

_LOGGER: Final = logging.getLogger(__name__)

BASE_INTEGRATION_OPTIONS_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_FORCE_LOCK_ICONS, default=False): cv.boolean,
        vol.Optional(
            CONF_EFFECTIVE_READ_TIMEOUT, default=DEFAULT_EFFECTIVE_READ_TIMEOUT
        ): cv.positive_float,
        vol.Optional(
            CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL
        ): cv.positive_float,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
    },
    extra=vol.REMOVE_EXTRA,
)

INTEGRATION_OPTIONS_SCHEMA: Final = BASE_INTEGRATION_OPTIONS_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DISABLE_WEBSOCKETS, default=DEFAULT_DISABLE_WEBSOCKETS
        ): cv.boolean,
    },
    extra=vol.REMOVE_EXTRA,
)
"""Schema for integration options coming from saved entry"""

DEVICE_OPTIONS_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_FUEL_IS_LITERS, default=False): cv.boolean,
        vol.Optional(CONF_MILEAGE_MILES, default=False): cv.boolean,
        vol.Optional(CONF_MILEAGE_CAN_MILES, default=False): cv.boolean,
        vol.Optional(CONF_OFFLINE_AS_UNAVAILABLE, default=False): cv.boolean,
        vol.Optional(CONF_IGNORE_WS_COORDINATES, default=False): cv.boolean,
        vol.Optional(CONF_ENGINE_STATE_BY_RPM, default=False): cv.boolean,
        vol.Optional(CONF_RPM_COEFFICIENT, default=1.0): cv.positive_float,
        vol.Optional(CONF_RPM_OFFSET, default=0.0): vol.Coerce(float),
        vol.Optional(
            CONF_COORDINATES_DEBOUNCE,
            default=DEFAULT_COORDINATES_SMOOTHING,
        ): cv.positive_float,
        vol.Optional(CONF_CUSTOM_CURSOR_TYPE, default=DEFAULT_CURSOR_TYPE): vol.In(
            (
                DEFAULT_CURSOR_TYPE,
                DISABLED_CURSOR_TYPE,
                *sorted(IMAGE_REGISTRY.keys()),
            )
        ),
        vol.Optional(CONF_DISABLE_CURSOR_ROTATION, default=False): cv.boolean,
        vol.Optional(CONF_IGNORE_UPDATES_ENGINE_OFF, default=list): cv.multi_select(
            [
                f"{platform}__{entity_type.key}"
                for platform in PLATFORMS
                for entity_type in importlib.import_module(
                    f"custom_components.pandora_cas.{platform}"
                ).ENTITY_TYPES
            ]
        ),
    },
    extra=vol.REMOVE_EXTRA,
)
"""Schema for device options coming from saved entry"""

ENTRY_OPTIONS_SCHEMA: Final = INTEGRATION_OPTIONS_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default=dict): {cv.string: DEVICE_OPTIONS_SCHEMA}},
    extra=vol.REMOVE_EXTRA,
)
"""Schema for configuration entry options coming from saved entry"""

ENTRY_DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_ACCESS_TOKEN): cv.string,
    },
    extra=vol.REMOVE_EXTRA,
)
"""Schema for configuration entry data coming from saved entry"""

CONFIG_ENTRY_SCHEMA: Final = vol.All(
    *(cv.removed(platform_id, raise_if_present=False) for platform_id in PLATFORMS),
    cv.removed(CONF_RPM_COEFFICIENT, raise_if_present=False),
    cv.removed(CONF_RPM_OFFSET, raise_if_present=False),
    *(
        cv.removed(str(schema_key), raise_if_present=False)
        for schema_key in INTEGRATION_OPTIONS_SCHEMA.schema
    ),
    ENTRY_DATA_SCHEMA,
)
"""Schema for configuration data coming from YAML"""

CONFIG_SCHEMA: Final = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            cv.remove_falsy,
            [CONFIG_ENTRY_SCHEMA],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)
"""Schema for domain data coming from YAML"""


def _determine_command_by_slug(command_slug: str) -> int:
    enum_member = command_slug.upper().strip()
    for key, value in CommandID.__members__.items():
        if key == enum_member:
            return value

    raise vol.Invalid("invalid command identifier")


SERVICE_PREDEFINED_COMMAND_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_DEVICE_ID, ATTR_DEVICE_ID): cv.string,
            vol.Exclusive(ATTR_ID, ATTR_DEVICE_ID): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.deprecated(ATTR_ID, ATTR_DEVICE_ID),
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)

SERVICE_REMOTE_COMMAND = "remote_command"
SERVICE_REMOTE_COMMAND_SCHEMA = vol.All(
    SERVICE_PREDEFINED_COMMAND_SCHEMA,
    vol.Schema(
        {
            vol.Required(ATTR_COMMAND_ID): vol.Any(
                cv.positive_int,
                vol.All(cv.string, _determine_command_by_slug),
            ),
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


def iterate_commands_to_register(cls=CommandID):
    for key, value in cls.__members__.items():
        yield slugify(key.lower()), value.value


async def _async_execute_remote_command(
    hass: HomeAssistant,
    call: "ServiceCall",
    command_id: int | CommandID | None = None,
    params: Mapping[str, Any] | None = None,
) -> None:
    _LOGGER.debug(f"Called service '{call.service}' with data: {dict(call.data)}")

    # Infer device identifier
    try:
        device_id = int(call.data[ATTR_DEVICE_ID])
    except (TypeError, ValueError, LookupError):
        dr = device_registry.async_get(hass)
        device_entry = dr.async_get(call.data[ATTR_DEVICE_ID])
        for domain, value in device_entry.identifiers:
            if domain == DOMAIN:
                try:
                    device_id = int(value)
                except (TypeError, ValueError):
                    pass
                else:
                    break
        else:
            raise HomeAssistantError(
                f"Invalid device ID '{call.data[ATTR_DEVICE_ID]}' provided"
            )

    # Find device by identifier
    for config_entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        try:
            device = coordinator.account.devices[device_id]
        except KeyError:
            continue
        _LOGGER.debug(
            f"Found device '{device}' on coordinator '{coordinator}' for '{call.service}' service call"
        )
        break
    else:
        raise HomeAssistantError(f"Device with ID '{device_id}' not found.")

    if command_id is None:
        command_id = call.data[ATTR_COMMAND_ID]

    result = device.async_remote_command(command_id, params, ensure_complete=False)
    if asyncio.iscoroutine(result):
        await result


@bind_hass
async def _async_register_services(hass: HomeAssistant) -> None:
    # register the remote services
    _register_service = hass.services.async_register

    _register_service(
        DOMAIN,
        SERVICE_REMOTE_COMMAND,
        partial(_async_execute_remote_command, hass),
        schema=SERVICE_REMOTE_COMMAND_SCHEMA,
    )

    for command_slug, command_id in iterate_commands_to_register():
        _LOGGER.debug(
            f"Registering remote command: {command_slug} (command_id={command_id})"
        )
        _register_service(
            DOMAIN,
            command_slug,
            partial(
                _async_execute_remote_command,
                hass,
                command_id=command_id,
            ),
            schema=SERVICE_PREDEFINED_COMMAND_SCHEMA,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Activate Pandora Car Alarm System component"""
    # Register services
    hass.async_create_task(_async_register_services(hass))

    # YAML configuration loader
    if not (domain_config := config.get(DOMAIN)):
        return True

    configured_users = {
        username: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if (username := entry.data.get(CONF_USERNAME)) is not None
    }
    for user_cfg in domain_config:
        username = user_cfg[CONF_USERNAME]
        try:
            entry = configured_users[username]
        except KeyError:
            _LOGGER.debug(f"Creating new entry for {username}")
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=user_cfg,
                )
            )
        else:
            if entry.source == SOURCE_IMPORT and user_cfg[
                CONF_PASSWORD
            ] != entry.data.get(CONF_PASSWORD):
                _LOGGER.debug(f"Migrating password into {entry.entry_id}")
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_PASSWORD: user_cfg[CONF_PASSWORD],
                    },
                )
            continue

    return True


class ConfigEntryLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that prefixes config entry ID."""

    def __init__(
        self,
        logger: logging.Logger = _LOGGER,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        if (config_entry or (config_entry := current_entry.get())) is None:
            raise RuntimeError("no context of config entry")
        super().__init__(logger, {"config_entry": config_entry})
        self.config_entry = config_entry

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        return "[%s] %s" % (self.config_entry.entry_id[-6:], msg), kwargs


def get_config_entry_language(entry: ConfigEntry) -> str:
    """Get web translations language from configuration entry options."""
    if entry.options is None:
        return DEFAULT_LANGUAGE
    return entry.options.get(CONF_LANGUAGE) or DEFAULT_LANGUAGE


def get_web_translations_value(
    hass: HomeAssistant, language: str, key: str
) -> str | None:
    """Retrieve value from web translations language dictionary."""
    try:
        web_translations = hass.data[DATA_WEB_TRANSLATIONS]
    except KeyError:
        return None

    try:
        return web_translations[language][key]
    except KeyError:
        if language != DEFAULT_LANGUAGE:
            return get_web_translations_value(hass, DEFAULT_LANGUAGE, key)
        raise


async def async_load_web_translations(
    hass: HomeAssistant, language: str, verify_ssl: bool = True
) -> dict[str, str]:
    """Load web translations."""
    if (language := language.lower()) == "last_update":
        raise ValueError("how?")

    try:
        # Retrieve initialized store
        store = hass.data[DATA_WEB_TRANSLATIONS_STORE]
    except KeyError:
        hass.data[DATA_WEB_TRANSLATIONS_STORE] = store = Store(
            hass,
            1,
            DATA_WEB_TRANSLATIONS,
        )

    try:
        # Retrieve cached data
        saved_data = hass.data[DATA_WEB_TRANSLATIONS]
    except KeyError:
        # Retrieve stored data
        saved_data = await store.async_load()

        # Provide fallback for corrupt or empty data
        if not isinstance(saved_data, dict):
            saved_data = {}

        # Cache loaded data
        hass.data[DATA_WEB_TRANSLATIONS] = saved_data

    language_data = None
    if saved_data:
        try:
            last_update = float(saved_data["last_update"][language])
        except (KeyError, ValueError, TypeError):
            _LOGGER.info(
                f"Data for language {language} is missing "
                f"valid timestamp information."
            )
        else:
            if (time() - last_update) > (7 * 24 * 60 * 60):
                _LOGGER.info(
                    f"Last data retrieval for language {language} "
                    f"occurred on {datetime.fromtimestamp(last_update).isoformat()}, "
                    f"assuming data is stale."
                )
            elif not isinstance((language_data := saved_data.get(language)), dict):
                _LOGGER.warning(
                    f"Data for language {language} is missing, "
                    f"assuming storage is corrupt."
                )
            else:
                _LOGGER.info(
                    f"Data for language {language} is recent, " f"no updates required."
                )
                return saved_data[language]
    else:
        _LOGGER.info("Translation data store initialization required.")

    _LOGGER.info(f"Will attempt to download translations for language: {language}")

    try:
        async with async_get_clientsession(hass, verify_ssl).get(
            f"https://p-on.ru/local/web/{language}.json",
        ) as response:
            new_data = await response.json()
    except (aiohttp.ClientError, JSONDecodeError):
        if isinstance((language_data := saved_data.get(language)), dict):
            _LOGGER.warning(
                f"Could not download translations for language "
                f"{language}, will fall back to stale data."
            )
            return language_data
        elif language == DEFAULT_LANGUAGE:
            _LOGGER.error(f"Failed loading fallback language")
            raise
        new_data = None

    # Use fallback web translations because decoded data is bad
    if not isinstance(new_data, dict):
        _LOGGER.error(
            f"Could not decode translations "
            f"for language {language}, falling "
            f"back to {DEFAULT_LANGUAGE}",
        )
        return await async_load_web_translations(
            hass,
            DEFAULT_LANGUAGE,
            verify_ssl,
        )

    if not isinstance(language_data, dict):
        saved_data[language] = language_data = {}

    # Fix-ups (QoL) for data
    for key, value in new_data.items():
        if value is None or not (value := str(value).strip()):
            continue
        if key.startswith("event-name-"):
            # Uppercase only first character
            value = value[0].upper() + value[1:]
        elif key.startswith("event-subname-"):
            # Lowercase only first character
            value = value[0].lower() + value[1:]
        language_data[key] = value

    saved_data.setdefault("last_update", {})[language] = time()

    await store.async_save(saved_data)

    _LOGGER.info(f"Data for language {language} updated successfully.")
    return language_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup configuration entry for Pandora Car Alarm System."""
    logger = ConfigEntryLoggerAdapter(_LOGGER)

    logger.info(f"Setting up config entry")

    # Prepare necessary data
    data = ENTRY_DATA_SCHEMA(dict(entry.data))
    options = ENTRY_OPTIONS_SCHEMA({} if entry.options is None else dict(entry.options))
    username = entry.data[CONF_USERNAME]
    access_token = data.get(CONF_ACCESS_TOKEN)

    # Instantiate account object
    account = PandoraOnlineAccount(
        username=username,
        password=data[CONF_PASSWORD],
        access_token=access_token,
        session=async_get_clientsession(hass, options[CONF_VERIFY_SSL]),
        logger=ConfigEntryLoggerAdapter,
    )

    # Perform authentication
    await async_run_pandora_coro(account.async_authenticate())

    # Load web translations
    # @TODO: make this a completely optional background job that runs until it is successful
    try:
        await async_load_web_translations(
            hass,
            get_config_entry_language(entry),
            options[CONF_VERIFY_SSL],
        )
    except BaseException as exc:
        _LOGGER.error(f"Translations download failed: {exc}", exc_info=exc)
        pass

    # Update access token if necessary
    if access_token != account.access_token:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: account.access_token,
            },
        )

    # Fetch devices
    await async_run_pandora_coro(account.async_refresh_devices())

    # Create update coordinator
    update_interval = None
    if not entry.pref_disable_polling:
        update_interval = timedelta(seconds=options[CONF_POLLING_INTERVAL])
        logger.debug(f"Setting up polling to refresh at {update_interval} interval")

    # Setup update coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator = (
        PandoraCASUpdateCoordinator(hass, account, update_interval, logger=logger)
    )
    await coordinator.async_config_entry_first_refresh()

    # Forward entry setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Create options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    logger.info("Finished config entry setup")

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Pandora CAS entry"""
    _LOGGER.info("Reloading configuration entry")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    logger = ConfigEntryLoggerAdapter(_LOGGER, entry)
    logger.info(f"Upgrading from version {entry.version}")

    args = {
        "data": (new_data := {**entry.data}),
        "options": (new_options := {**entry.options}),
    }

    devices_conf = new_options.setdefault(CONF_DEVICES, {})

    def _add_new_devices_option(option_name: str, default_value: Any = None):
        for _device in async_entries_for_config_entry(
            async_get_device_registry(hass), entry.entry_id
        ):
            try:
                _domain, _pandora_id = next(iter(_device.identifiers))
            except (StopIteration, TypeError, ValueError):
                continue
            else:
                devices_conf.setdefault(str(_pandora_id), {})[
                    option_name
                ] = default_value

    if entry.version < 3:
        for src in (new_data, new_options):
            # src.pop("polling_interval", None)
            src.pop("user_agent", None)
        entry.version = 3

    if entry.version < 5:
        # Update unique ID to user ID
        new_options.setdefault(CONF_VERIFY_SSL, True)
        account = PandoraOnlineAccount(
            username=new_data[CONF_USERNAME],
            password=new_data[CONF_PASSWORD],
            access_token=new_data.get(CONF_ACCESS_TOKEN),
            session=async_get_clientsession(
                hass, verify_ssl=new_options[CONF_VERIFY_SSL]
            ),
        )

        await async_run_pandora_coro(account.async_authenticate())

        new_data[CONF_ACCESS_TOKEN] = account.access_token
        args["unique_id"] = str(account.user_id)

        entry.version = 5

    if entry.version < 6:
        # Remove / migrate old device entry
        dev_reg = async_get_device_registry(hass)
        entries_to_update: dict[str | int, str] = {}
        for device_entry in tuple(dev_reg.devices.values()):
            for identifier in device_entry.identifiers:
                if len(identifier) != 2 or identifier[0] != DOMAIN:
                    continue
                pandora_id = identifier[1]
                try:
                    if isinstance(pandora_id, int):
                        # Find valid device for this pandora ID
                        remove_id = device_entry.id
                        entries_to_update.pop(str(pandora_id))
                    else:
                        # Find erroneous device for this pandora ID
                        remove_id = entries_to_update.pop(int(pandora_id))
                except KeyError:
                    entries_to_update[pandora_id] = device_entry.id
                except (TypeError, ValueError):
                    logger.warning(
                        f"[{entry.entry_id}] Device identifier {pandora_id} "
                        f"is not supported. Did it come from another "
                        f"integration?"
                    )
                else:
                    # Remove obsolete device if both found
                    logger.info(f"Removing obsolete device entry for {pandora_id}")
                    dev_reg.async_remove_device(remove_id)

        for pandora_id, device_id in entries_to_update.items():
            if isinstance(pandora_id, str):
                continue
            logger.info(f"Updating obsolete device entry for {pandora_id}")
            dev_reg.async_update_device(
                device_id,
                new_identifiers={(DOMAIN, str(pandora_id))},
            )

        entry.version = 6

    if entry.version < 9:
        # Transition per-entity options
        _add_new_devices_option(CONF_MILEAGE_MILES, False)
        _add_new_devices_option(CONF_MILEAGE_CAN_MILES, False)
        _add_new_devices_option(CONF_FUEL_IS_LITERS, False)
        _add_new_devices_option(CONF_ENGINE_STATE_BY_RPM, False)

        # Transition cursors
        devices_conf = new_options.setdefault(CONF_DEVICES)
        for pandora_id, cursor_type in (
            new_options.pop(CONF_CUSTOM_CURSORS, None) or {}
        ).items():
            devices_conf.setdefault(str(pandora_id), {})[
                CONF_CUSTOM_CURSOR_TYPE
            ] = cursor_type

        # Transition global offline_as_unavailable
        if (v := new_options.pop(CONF_OFFLINE_AS_UNAVAILABLE, None)) is not None:
            _add_new_devices_option(CONF_OFFLINE_AS_UNAVAILABLE, v)

        entry.version = 9

    if entry.version < 10:
        args["pref_disable_polling"] = True

        # Remove junk values
        new_options.pop(CONF_MILEAGE_CAN_MILES, None)
        new_options.pop(CONF_MILEAGE_MILES, None)
        new_options.pop(CONF_FUEL_IS_LITERS, None)

        # Add new integration config
        new_options.setdefault(CONF_DISABLE_WEBSOCKETS, False)

        # Add new device config
        _add_new_devices_option(CONF_IGNORE_WS_COORDINATES, False)
        _add_new_devices_option(
            CONF_COORDINATES_DEBOUNCE, DEFAULT_COORDINATES_SMOOTHING
        )
        entry.version = 10

    if entry.version < 11:
        new_options.setdefault(
            CONF_EFFECTIVE_READ_TIMEOUT,
            DEFAULT_EFFECTIVE_READ_TIMEOUT,
        )
        entry.version = 11

    if entry.version < 12:
        if CONF_POLLING_INTERVAL in new_options:
            new_options[CONF_POLLING_INTERVAL] = max(
                MIN_POLLING_INTERVAL, new_options[CONF_POLLING_INTERVAL] or -1
            )
        else:
            new_options[CONF_POLLING_INTERVAL] = DEFAULT_POLLING_INTERVAL * (
                5 if new_options[CONF_DISABLE_WEBSOCKETS] else 1
            )

        entry.version = 12

    if entry.version < 13:
        new_options.setdefault(
            CONF_LANGUAGE,
            DEFAULT_LANGUAGE,
        )

        entry.version = 13

    hass.config_entries.async_update_entry(entry, **args)

    _LOGGER.info(f"Upgraded configuration entry to version {entry.version}")

    return True


def event_enum_to_type(
    primary_event_id: PrimaryEventID | Type[PrimaryEventID],
) -> str:
    """Convert event ID to a slugified representation."""
    return slugify(primary_event_id.name.lower())


_T = TypeVar("_T")


async def async_run_pandora_coro(coro: Awaitable[_T]) -> _T:
    try:
        return await coro
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except MalformedResponseError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    except aiohttp.ClientError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    except (OSError, TimeoutError) as exc:
        raise ConfigEntryNotReady(str(exc)) from exc


class PandoraCASUpdateCoordinator(
    DataUpdateCoordinator[tuple[bool, Mapping[int, Mapping[str, Any]]]]
):
    def __init__(
        self,
        hass: HomeAssistant,
        account: PandoraOnlineAccount,
        update_interval: timedelta | None = None,
        logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
    ) -> None:
        self.account = account
        self._device_configs = {}
        super().__init__(hass, logger, name=DOMAIN, update_interval=update_interval)

    async def async_config_entry_first_refresh(self) -> None:
        await super().async_config_entry_first_refresh()

        disable_websockets = (self.config_entry.options or {}).get(
            CONF_DISABLE_WEBSOCKETS
        )
        if disable_websockets is None:
            disable_websockets = DEFAULT_DISABLE_WEBSOCKETS
        if disable_websockets:
            return

        self.logger.debug(f"Setting up background WS listener task")
        self.config_entry.async_create_background_task(
            self.hass,
            self.async_listen_config_entry(),
            f"Pandora CAS entry {self.config_entry.entry_id} listener",
        )

    @property
    def is_last_update_ws(self) -> bool:
        return self.data and self.data[0]

    def get_device_config(self, device_id: str | int) -> dict[str, Any]:
        device_id = str(device_id)
        try:
            return self._device_configs[device_id]
        except KeyError:
            config = DEVICE_OPTIONS_SCHEMA(
                self.config_entry.options.get(CONF_DEVICES, {}).get(device_id, {})
            )
            self._device_configs[device_id] = config
            return config

    async def async_listen_config_entry(self):
        effective_read_timeout = self.config_entry.options.get(
            CONF_EFFECTIVE_READ_TIMEOUT
        )
        if effective_read_timeout is None:
            effective_read_timeout = DEFAULT_EFFECTIVE_READ_TIMEOUT
        effective_read_timeout = max(MIN_EFFECTIVE_READ_TIMEOUT, effective_read_timeout)

        while True:
            try:
                await self.account.async_listen_for_updates(
                    state_callback=self._handle_ws_state,
                    command_callback=self._handle_ws_command,
                    event_callback=self._handle_ws_event,
                    point_callback=self._handle_ws_point,
                    update_settings_callback=self._handle_ws_settings,
                    effective_read_timeout=effective_read_timeout,
                    auto_reauth=True,
                    auto_restart=True,
                )
            except asyncio.CancelledError:
                raise
            except AuthenticationError as exc:
                raise ConfigEntryAuthFailed(str(exc)) from exc
            except BaseException as exc:
                self.logger.warning(
                    f"Exception occurred on WS listener: {exc}",
                    exc_info=exc,
                )
                continue

    # noinspection PyUnusedLocal
    @callback
    def _handle_ws_state(
        self,
        device: PandoraOnlineDevice,
        state: CurrentState,
        state_args: Mapping[str, Any],
    ) -> None:
        self.logger.debug(
            f"Received WS state update for device {device.device_id}: {state_args}"
        )
        self.async_set_updated_data((True, {device.device_id: state_args}))

    @callback
    def _handle_ws_command(
        self,
        device: PandoraOnlineDevice,
        command_id: int,
        result: int,
        reply: Any,
    ) -> None:
        """Pass command execution data to Home Assistant event bus."""
        self.logger.debug(
            f"Firing command {command_id} event for device {device.device_id}"
        )
        self.hass.bus.async_fire(
            EVENT_TYPE_COMMAND,
            {
                ATTR_DEVICE_ID: device.device_id,
                ATTR_COMMAND_ID: command_id,
                ATTR_RESULT: result,
                ATTR_REPLY: reply,
            },
        )

    @callback
    def _handle_ws_event(
        self,
        device: PandoraOnlineDevice,
        event: "TrackingEvent",
    ) -> None:
        """Pass event data to Home Assistant event bus."""
        self.logger.debug(
            f"Firing event {EVENT_TYPE_EVENT}[{event.event_id_primary}/"
            f"{event.event_id_secondary}] for device {event.device_id}"
        )
        language = get_config_entry_language(self.config_entry)

        self.hass.bus.async_fire(
            EVENT_TYPE_EVENT,
            {
                CONF_EVENT_TYPE: event_enum_to_type(event.primary_event_enum),
                ATTR_DEVICE_ID: device.device_id,
                ATTR_EVENT_ID_PRIMARY: (p := event.event_id_primary),
                ATTR_EVENT_ID_SECONDARY: (s := event.event_id_secondary),
                ATTR_TITLE_PRIMARY: (
                    None
                    if p is None
                    else get_web_translations_value(
                        self.hass,
                        language,
                        f"event-name-{p}",
                    )
                ),
                ATTR_TITLE_SECONDARY: (
                    None
                    if s is None
                    else get_web_translations_value(
                        self.hass,
                        language,
                        f"event-subname-{p}-{s}",
                    )
                ),
                ATTR_LATITUDE: event.latitude,
                ATTR_LONGITUDE: event.longitude,
                "gsm_level": event.gsm_level,
                "fuel": event.fuel,
                "exterior_temperature": event.exterior_temperature,
                "engine_temperature": event.engine_temperature,
            },
        )

        # @TODO: add time_fired parameter

    # noinspection PyUnusedLocal
    @callback
    def _handle_ws_point(
        self,
        device: PandoraOnlineDevice,
        point: TrackingPoint,
        state: CurrentState | None = None,
        state_args: Mapping[str, Any] | None = None,
    ) -> None:
        self.logger.debug(
            f"Firing event {EVENT_TYPE_POINT}[{point.track_id}/"
            f"{point.timestamp}] for device {point.device_id}"
        )
        self.hass.bus.async_fire(
            EVENT_TYPE_POINT,
            {
                ATTR_DEVICE_ID: point.device_id,
                ATTR_TIMESTAMP: point.timestamp,
                ATTR_TRACK_ID: point.track_id,
                "fuel": point.fuel,
                "speed": point.speed,
                "max_speed": point.max_speed,
                "length": point.length,
            },
        )

        if state_args:
            self.logger.debug(f"Updating device {point.device_id} state through point")
            self._handle_ws_state(device, device.state, state_args)

    # noinspection PyUnusedLocal
    @callback
    def _handle_ws_settings(
        self,
        device: PandoraOnlineDevice,
        update_settings: Mapping[str, Any],
    ) -> None:
        """Pass event data to Home Assistant event bus."""
        # logger.debug(
        #     f"Firing event {EVENT_TYPE_EVENT}[{event.event_id_primary}/"
        #     f"{event.event_id_secondary}] for device {event.device_id}"
        # )
        # hass.bus.async_fire(
        #     EVENT_TYPE_EVENT,
        #     {
        #         CONF_EVENT_TYPE: event_enum_to_type(PrimaryEventID.SETTINGS_CHANGED),
        #         ATTR_DEVICE_ID: device.device_id,
        #         "event_id_primary": int(PrimaryEventID.SETTINGS_CHANGED),
        #         "event_id_secondary": event.event_id_secondary,
        #     },
        # )

        self.logger.debug(
            "Update-Settings event received from WS, but I don't yet"
            "know what to do with it. Pls suggest."
        )

        # @TODO: add time_fired parameter
        pass

    async def _async_update_data(
        self,
    ) -> tuple[Literal[False], Mapping[int, Mapping[str, Any]]]:
        """Fetch data for sub-entities."""
        # @TODO: manual polling updates!
        try:
            try:
                (
                    updates,
                    events,
                ) = await self.account.async_request_updates()
            except AuthenticationError:
                try:
                    await self.account.async_authenticate()
                    (
                        updates,
                        events,
                    ) = await self.account.async_request_updates()
                except AuthenticationError as exc:
                    raise ConfigEntryAuthFailed(
                        "Authentication failed during fetching"
                    ) from exc
        except MalformedResponseError as exc:
            raise UpdateFailed("Malformed response retrieved") from exc

        return False, updates
