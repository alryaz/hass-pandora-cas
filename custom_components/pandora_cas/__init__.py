"""Initialization script for Pandora Car Alarm System component."""

__all__ = (
    "BASE_CONFIG_ENTRY_SCHEMA",
    "CONFIG_SCHEMA",
    "DEVICE_OPTIONS_SCHEMA",
    "INTEGRATION_OPTIONS_SCHEMA",
    "PandoraCASUpdateCoordinator",
    "SERVICE_REMOTE_COMMAND",
    "async_migrate_entry",
    "async_run_pandora_coro",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
)

import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import Any, Mapping, Type, TypeVar, Awaitable, Dict, Tuple, Literal

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
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
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
    async_entries_for_config_entry,
)
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

_LOGGER = logging.getLogger(__name__)

INTEGRATION_OPTIONS_SCHEMA: Final = vol.Schema(
    {
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_DISABLE_WEBSOCKETS, default=False): cv.boolean,
        vol.Optional(CONF_DISABLE_POLLING, default=False): cv.boolean,
    }
)

BASE_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
).extend(INTEGRATION_OPTIONS_SCHEMA.schema)

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
            CONF_COORDINATES_DEBOUNCE, default=DEFAULT_COORDINATES_SMOOTHING
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
    },
    extra=vol.ALLOW_EXTRA,
)


CONFIG_ENTRY_SCHEMA = vol.All(
    *(
        cv.removed(platform_id, raise_if_present=False)
        for platform_id in PLATFORMS
    ),
    cv.removed(CONF_RPM_COEFFICIENT, raise_if_present=False),
    cv.removed(CONF_RPM_OFFSET, raise_if_present=False),
    BASE_CONFIG_ENTRY_SCHEMA,
)

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
            raise ValueError("Invalid device ID provided")

        device = None
        for config_entry_id, coordinators in hass.data.get(DOMAIN, {}).items():
            try:
                device = coordinators[device_id].device
            except KeyError:
                continue
            break

        if device is None:
            raise ValueError(f"Device with ID '{device_id}' not found")

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
            entry = configured_users[user_cfg]
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
            if (
                entry.source == SOURCE_IMPORT
                and not CONF_PASSWORD not in entry.data
            ):
                _LOGGER.debug(f"Migrating password into {entry.entry_id}")
                hass.config_entries.async_update_entry(
                    entry,
                    data={**user_cfg, **entry.data},
                )
            continue

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup configuration entry for Pandora Car Alarm System."""
    _LOGGER.debug(f'Setting up entry "{entry.entry_id}"')

    # Instantiate account object
    account = PandoraOnlineAccount(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        session=async_get_clientsession(
            hass, verify_ssl=entry.options[CONF_VERIFY_SSL]
        ),
    )

    # Perform authentication
    await async_run_pandora_coro(account.async_authenticate())

    # Update access token if necessary
    if entry.data.get(CONF_ACCESS_TOKEN) != account.access_token:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ACCESS_TOKEN: account.access_token}
        )

    # Fetch devices
    await async_run_pandora_coro(account.async_refresh_devices())

    # Create update coordinator
    update_interval = None
    if not entry.pref_disable_polling:
        update_interval = timedelta(
            seconds=(5 if entry.options[CONF_DISABLE_WEBSOCKETS] else 30)
        )

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = coordinator = PandoraCASUpdateCoordinator(
        hass, account, update_interval
    )
    await coordinator.async_config_entry_first_refresh()

    # Start listening for updates if enabled
    if not entry.options[CONF_DISABLE_WEBSOCKETS]:

        def _state_changes_listener(
            device: PandoraOnlineDevice,
            _: CurrentState,
            new_state_values: Mapping[str, Any],
        ) -> None:
            _LOGGER.debug(
                f"Received WebSockets state update for "
                f"device {device.device_id}: {new_state_values}"
            )
            coordinator.async_set_updated_data(
                (True, {device.device_id: new_state_values})
            )

        # noinspection PyTypeChecker
        hass.data.setdefault(DATA_LISTENERS, {})[
            entry.entry_id
        ] = hass.loop.create_task(
            account.async_listen_for_updates(
                state_callback=_state_changes_listener,
                command_callback=partial(async_command_delegator, hass),
                event_callback=partial(async_event_delegator, hass),
                point_callback=partial(async_point_delegator, hass),
                update_settings_callback=partial(
                    async_update_settings_delegator, hass
                ),
                auto_restart=True,
            ),
            name=f"Pandora CAS entry {entry.entry_id} listener",
        )

    # Forward entry setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Create options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Pandora CAS entry"""
    _LOGGER.info("Reloading configuration entry")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload configuration entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        # Cancel WebSockets listener
        if listener := hass.data.get(DATA_LISTENERS, {}).pop(
            entry.entry_id, None
        ):
            listener.cancel()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(f"Upgrading configuration entry from version {entry.version}")

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
            src.pop("polling_interval", None)
            src.pop("user_agent", None)
        entry.version = 3

    if entry.version < 5:
        # Update unique ID to user ID
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
                    _LOGGER.warning(
                        f"[{entry.entry_id}] Device identifier {pandora_id} "
                        f"is not supported. Did it come from another "
                        f"integration?"
                    )
                else:
                    # Remove obsolete device if both found
                    _LOGGER.info(
                        f"[{entry.entry_id}] Removing obsolete device"
                        f"entry for {pandora_id}"
                    )
                    dev_reg.async_remove_device(remove_id)

        for pandora_id, device_id in entries_to_update.items():
            if isinstance(pandora_id, str):
                continue
            _LOGGER.info(
                f"[{entry.entry_id}] Updating obsolete device entry"
                f"for {pandora_id}"
            )
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

    hass.config_entries.async_update_entry(entry, **args)

    _LOGGER.info(f"Upgraded configuration entry to version {entry.version}")

    return True


def event_enum_to_type(
    primary_event_id: PrimaryEventID | Type[PrimaryEventID],
) -> str:
    """Convert event ID to a slugified representation."""
    return slugify(primary_event_id.name.lower())


def async_command_delegator(
    hass: HomeAssistant,
    device: PandoraOnlineDevice,
    command_id: int,
    result: int,
    reply: Any,
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


def async_event_delegator(
    hass: HomeAssistant, device: PandoraOnlineDevice, event: TrackingEvent
) -> None:
    """Pass event data to Home Assistant event bus."""
    hass.bus.async_fire(
        EVENT_TYPE_EVENT,
        {
            "event_type": event_enum_to_type(event.primary_event_enum),
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


def async_update_settings_delegator(
    hass: HomeAssistant, device: PandoraOnlineDevice, event: TrackingEvent
) -> None:
    """Pass event data to Home Assistant event bus."""
    hass.bus.async_fire(
        EVENT_TYPE_EVENT,
        {
            "event_type": event_enum_to_type(PrimaryEventID.SETTINGS_CHANGED),
            ATTR_DEVICE_ID: device.device_id,
            "event_id_primary": int(PrimaryEventID.SETTINGS_CHANGED),
            "event_id_secondary": event.event_id_secondary,
        },
    )

    # @TODO: add time_fired parameter


# noinspection PyUnusedLocal
def async_point_delegator(
    hass: HomeAssistant, device: PandoraOnlineDevice, point: TrackingPoint
) -> None:
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


_T = TypeVar("_T")


async def async_run_pandora_coro(coro: Awaitable[_T]) -> _T:
    try:
        return await coro
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed("Authentication failed") from exc
    except MalformedResponseError as exc:
        raise ConfigEntryNotReady("Server responds erroneously") from exc
    except (OSError, aiohttp.ClientError, TimeoutError) as exc:
        raise ConfigEntryNotReady("Timed out while authenticating") from exc


class PandoraCASUpdateCoordinator(
    DataUpdateCoordinator[Tuple[bool, Mapping[int, Mapping[str, Any]]]]
):
    def __init__(
        self,
        hass: HomeAssistant,
        account: PandoraOnlineAccount,
        update_interval: timedelta | None = None,
    ) -> None:
        self.account = account
        self._device_configs = {}
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=update_interval
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
                updates, events = await self.account.async_request_updates()
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
