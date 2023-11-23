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
from datetime import timedelta
from functools import partial
from json import JSONDecodeError
from typing import (
    Any,
    Mapping,
    Type,
    TypeVar,
    Awaitable,
    Tuple,
    Literal,
    Optional,
    MutableMapping,
    Final,
)

import aiohttp
from time import time
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
)
from homeassistant.core import ServiceCall, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
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

from custom_components.pandora_cas.api import (
    AuthenticationError,
    CommandID,
    CurrentState,
    DEFAULT_USER_AGENT,
    PandoraOnlineAccount,
    PandoraOnlineDevice,
    PandoraOnlineException,
    TrackingEvent,
    TrackingPoint,
    Features,
    MalformedResponseError,
    PrimaryEventID,
)
from custom_components.pandora_cas.const import *
from custom_components.pandora_cas.tracker_images import IMAGE_REGISTRY

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
    },
    extra=vol.REMOVE_EXTRA,
)

INTEGRATION_OPTIONS_SCHEMA: Final = BASE_INTEGRATION_OPTIONS_SCHEMA.extend(
    {
        vol.Optional(CONF_DISABLE_WEBSOCKETS, default=False): cv.boolean,
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
        vol.Optional(
            CONF_CUSTOM_CURSOR_TYPE, default=DEFAULT_CURSOR_TYPE
        ): vol.In(
            (
                DEFAULT_CURSOR_TYPE,
                DISABLED_CURSOR_TYPE,
                *sorted(IMAGE_REGISTRY.keys()),
            )
        ),
        vol.Optional(CONF_DISABLE_CURSOR_ROTATION, default=False): cv.boolean,
        vol.Optional(
            CONF_IGNORE_UPDATES_ENGINE_OFF, default=list
        ): cv.multi_select(
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

ENTRY_OPTIONS_SCHEMA: Final = vol.All(
    lambda x: {} if x is None else dict(x),
    INTEGRATION_OPTIONS_SCHEMA.extend(
        {
            vol.Optional(CONF_DEVICES, default=dict): {
                cv.string: DEVICE_OPTIONS_SCHEMA
            }
        },
        extra=vol.REMOVE_EXTRA,
    ),
)
"""Schema for configuration entry options coming from saved entry"""

ENTRY_DATA_SCHEMA: Final = vol.All(
    lambda x: {} if x is None else dict(x),
    vol.Schema(
        {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_ACCESS_TOKEN): cv.string,
        },
        extra=vol.REMOVE_EXTRA,
    ),
)

"""Schema for configuration entry data coming from saved entry"""

CONFIG_ENTRY_SCHEMA: Final = vol.All(
    *(
        cv.removed(platform_id, raise_if_present=False)
        for platform_id in PLATFORMS
    ),
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


@bind_hass
async def _async_register_services(hass: HomeAssistant) -> None:
    async def _execute_remote_command(
        call: "ServiceCall", command_id: int | CommandID | None = None
    ) -> None:
        _LOGGER.debug(
            f"Called service '{call.service}' with data: {dict(call.data)}"
        )

        try:
            device_id = int(call.data[ATTR_DEVICE_ID])
        except (TypeError, ValueError, LookupError):
            raise HomeAssistantError("Invalid device ID provided")

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
            raise HomeAssistantError(
                f"Device with ID '{device_id}' not found."
            )

        if command_id is None:
            command_id = call.data[ATTR_COMMAND_ID]

        result = device.async_remote_command(command_id, ensure_complete=False)
        if asyncio.iscoroutine(result):
            await result

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


WEB_TRANSLATIONS_FALLBACK_LANGUAGE: Final = "en"

DATA_WEB_TRANSLATIONS_STORE: Final = f"{DOMAIN}_web_translations_store"
DATA_WEB_TRANSLATIONS: Final = f"{DOMAIN}_web_translations"

async def async_load_web_translations(hass: HomeAssistant, language: str = "ru", verify_ssl: bool = True) -> dict[str, str]:
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
        hass.data[DATA_WEB_TRANSLATIONS] = saved_data = await store.async_load()

    language_data = None
    if isinstance(saved_data, dict):
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
                    f"Data for language {language} is recent, "
                    f"no updates required."
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
        elif language == EVENT_TITLE_FALLBACK_LANGUAGE:
            _LOGGER.error(
                f"Failed loading fallback language"
            )
            raise
        _LOGGER.error(
            f"Could not decode translations "
            f"for language {language}, falling "
            f"back to {EVENT_TITLE_FALLBACK_LANGUAGE}",
        )
        return await async_load_web_translations(
            hass,
            EVENT_TITLE_FALLBACK_LANGUAGE,
            verify_ssl,
        )

    if not isinstance(language_data, dict):
        if not isinstance(saved_data, dict):
            saved_data = {}
        saved_data[language] = language_data = {}

    # Fix-ups (QoL) for data
    for key, value in language_data.items():
        if value is None or not (value := str(value).strip()):
            continue
        if key.startswith('event-name-'):
            # Uppercase only first character
            value = value[0].upper() + value[1:]
        elif key.startswith('event-subname-'):
            # Lowercase only first character
            value = value[0].lower() + value[1:]
        language_data[key] = value

    saved_data.setdefault("last_update", {})[language] = time()

    await store.async_save(saved_data)
    
    _LOGGER.info(
        f"Data for language {language} updated successfully."
    )
    return language_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup configuration entry for Pandora Car Alarm System."""
    logger = ConfigEntryLoggerAdapter(_LOGGER)

    logger.info(f"Setting up config entry")

    # Prepare necessary data
    data = ENTRY_DATA_SCHEMA(entry.data)
    options = ENTRY_OPTIONS_SCHEMA(entry.options)
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

    # @TODO: make this a completely optional background job
    try:
        await async_load_web_translations(hass, "ru", options[CONF_VERIFY_SSL])
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
        logger.debug(
            f"Setting up polling to refresh at {update_interval} interval"
        )

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = coordinator = PandoraCASUpdateCoordinator(
        hass, account, update_interval, logger=logger
    )
    await coordinator.async_config_entry_first_refresh()

    # Start listening for updates if enabled
    if not options[CONF_DISABLE_WEBSOCKETS]:

        async def _listen_configuration_entry():
            callback_args = dict(
                state_callback=partial(
                    async_state_delegator, hass, entry, logger=logger
                ),
                command_callback=partial(
                    async_command_delegator, hass, entry, logger=logger
                ),
                event_callback=partial(
                    async_event_delegator, hass, entry, logger=logger
                ),
                point_callback=partial(
                    async_point_delegator, hass, entry, logger=logger
                ),
                update_settings_callback=partial(
                    async_update_settings_delegator, hass, logger=logger
                ),
                effective_read_timeout=max(
                    MIN_EFFECTIVE_READ_TIMEOUT,
                    options[CONF_EFFECTIVE_READ_TIMEOUT],
                ),
                auto_restart=True,
                auto_reauth=True,
            )
            while True:
                try:
                    await account.async_listen_for_updates(**callback_args)
                except asyncio.CancelledError:
                    raise
                except AuthenticationError as exc:
                    raise ConfigEntryAuthFailed(str(exc)) from exc
                except BaseException as exc:
                    _LOGGER.warning(
                        f"Exception occurred on WS listener "
                        f"for entry {entry.entry_id}: {exc}",
                        exc_info=exc,
                    )
                    continue

        # noinspection PyTypeChecker
        entry.async_create_background_task(
            hass,
            _listen_configuration_entry(),
            f"Pandora CAS entry {entry.entry_id} listener",
        )

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
                    logger.info(
                        f"Removing obsolete device entry for {pandora_id}"
                    )
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
        if (
            v := new_options.pop(CONF_OFFLINE_AS_UNAVAILABLE, None)
        ) is not None:
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

    if entry.version < 11:
        new_options[
            CONF_EFFECTIVE_READ_TIMEOUT
        ] = DEFAULT_EFFECTIVE_READ_TIMEOUT

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

    hass.config_entries.async_update_entry(entry, **args)

    _LOGGER.info(f"Upgraded configuration entry to version {entry.version}")

    return True


def event_enum_to_type(
    primary_event_id: PrimaryEventID | Type[PrimaryEventID],
) -> str:
    """Convert event ID to a slugified representation."""
    return slugify(primary_event_id.name.lower())


@callback
def async_state_delegator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: PandoraOnlineDevice,
    _: CurrentState,
    state_args: Mapping[str, Any],
    *,
    logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
) -> None:
    logger.debug(
        f"Received WebSockets state update for "
        f"device {device.device_id}: {state_args}"
    )
    try:
        coordinator = hass.data[DOMAIN][entry.entry_id]
    except LookupError:
        logger.error("Coordinator not found")
    else:
        coordinator.async_set_updated_data(
            (True, {device.device_id: state_args})
        )


# noinspection PyUnusedLocal
@callback
def async_command_delegator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: PandoraOnlineDevice,
    command_id: int,
    result: int,
    reply: Any,
    *,
    logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
) -> None:
    """Pass command execution data to Home Assistant event bus."""
    hass.bus.async_fire(
        EVENT_TYPE_COMMAND,
        {
            "device_id": device.device_id,
            "command_id": command_id,
            "result": result,
            "reply": reply,
        },
    )


# noinspection PyUnusedLocal
@callback
def async_event_delegator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: PandoraOnlineDevice,
    event: TrackingEvent,
    *,
    logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
) -> None:
    """Pass event data to Home Assistant event bus."""
    logger.debug(
        f"Firing event {EVENT_TYPE_EVENT}[{event.event_id_primary}/"
        f"{event.event_id_secondary}] for device {event.device_id}"
    )
    hass.bus.async_fire(
        EVENT_TYPE_EVENT,
        {
            CONF_EVENT_TYPE: event_enum_to_type(event.primary_event_enum),
            ATTR_DEVICE_ID: device.device_id,
            "event_id_primary": event.event_id_primary,
            "event_id_secondary": event.event_id_secondary,
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
def async_update_settings_delegator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: PandoraOnlineDevice,
    update_settings: Mapping[str, Any],
    *,
    logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
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

    logger.debug(
        "Update-Settings event received from WS, but I don't yet"
        "know what to do with it. Pls suggest."
    )

    # @TODO: add time_fired parameter
    pass


# noinspection PyUnusedLocal
def async_point_delegator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: PandoraOnlineDevice,
    point: TrackingPoint,
    state: Optional[CurrentState],
    state_args: Optional[Mapping[str, Any]],
    *,
    logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
) -> None:
    logger.debug(
        f"Firing event {EVENT_TYPE_POINT}[{point.track_id}/"
        f"{point.timestamp}] for device {point.device_id}"
    )
    hass.bus.async_fire(
        EVENT_TYPE_POINT,
        {
            "device_id": point.device_id,
            "timestamp": point.timestamp,
            "track_id": point.track_id,
            "fuel": point.fuel,
            "speed": point.speed,
            "max_speed": point.max_speed,
            "length": point.length,
        },
    )

    if state_args:
        logger.debug(f"Updating device {point.device_id} state through point")
        async_state_delegator(
            hass, entry, device, state, state_args, logger=logger
        )


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
    DataUpdateCoordinator[Tuple[bool, Mapping[int, Mapping[str, Any]]]]
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
        super().__init__(
            hass, logger, name=DOMAIN, update_interval=update_interval
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
                self.config_entry.options.get(CONF_DEVICES, {}).get(
                    device_id, {}
                )
            )
            self._device_configs[device_id] = config
            return config

    async def _async_update_data(
        self,
    ) -> Tuple[Literal[False], Mapping[int, Mapping[str, Any]]]:
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
