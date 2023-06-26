"""Initialization script for Pandora Car Alarm System component."""

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "async_migrate_entry",
    "CONFIG_SCHEMA",
    "SERVICE_REMOTE_COMMAND",
]

import asyncio
import logging
from datetime import timedelta
from functools import partial
from typing import (
    Any,
    Mapping,
    Optional,
    Union,
)

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
    CONF_VERIFY_SSL,
    CONF_ACCESS_TOKEN,
)
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, UNDEFINED
from homeassistant.loader import bind_hass
from homeassistant.util import slugify

from custom_components.pandora_cas.api import (
    AuthenticationException,
    CommandID,
    CurrentState,
    DEFAULT_USER_AGENT,
    PandoraOnlineAccount,
    PandoraOnlineDevice,
    PandoraOnlineException,
    TrackingEvent,
    TrackingPoint,
    Features,
)
from custom_components.pandora_cas.config_flow import (
    async_authenticate_account,
)
from custom_components.pandora_cas.entity import (
    PandoraCASEntity,
    PandoraCASUpdateCoordinator,
)
from custom_components.pandora_cas.const import *

MIN_POLLING_INTERVAL = timedelta(seconds=10)
DEFAULT_POLLING_INTERVAL = timedelta(minutes=1)
DEFAULT_EXECUTION_DELAY = timedelta(seconds=15)

PLATFORMS: Final = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
)

_LOGGER = logging.getLogger(__name__)

_BASE_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

CONFIG_ENTRY_SCHEMA = vol.All(
    *(
        cv.removed(platform_id, raise_if_present=False)
        for platform_id in PLATFORMS
    ),
    cv.removed("rpm_coefficient", raise_if_present=False),
    cv.removed("rpm_offset", raise_if_present=False),
    _BASE_CONFIG_ENTRY_SCHEMA,
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
        call: "ServiceCall", command_id: Optional[Union[int, CommandID]] = None
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

    # create account object
    account = PandoraOnlineAccount(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        session=async_get_clientsession(
            hass, verify_ssl=entry.options[CONF_VERIFY_SSL]
        ),
    )

    await async_authenticate_account(account)

    if entry.data.get(CONF_ACCESS_TOKEN) != account.access_token:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ACCESS_TOKEN: account.access_token}
        )

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = coordinator = PandoraCASUpdateCoordinator(hass, account=account)

    # create account updater
    async def _state_changes_listener(
        device: PandoraOnlineDevice,
        _: CurrentState,
        new_state_values: Mapping[str, Any],
    ):
        _LOGGER.debug(
            f"Received WebSockets state update for "
            f"device {device.device_id}: {new_state_values}"
        )

        coordinator.async_set_updated_data(
            {device.device_id: new_state_values}
        )

    async def _command_execution_listener(
        device: PandoraOnlineDevice,
        command_id: int,
        result: int,
        reply: Any,
    ):
        _LOGGER.debug(
            "Received command execution result: %s / %s / %s",
            command_id,
            result,
            reply,
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
    if not entry.options.get(CONF_DISABLE_WEBSOCKETS):
        hass.data.setdefault(DATA_LISTENERS, {})[
            entry.entry_id
        ] = hass.loop.create_task(
            account.async_listen_for_updates(
                state_callback=_state_changes_listener,
                command_callback=_command_execution_listener,
                event_callback=_event_catcher_listener,
                point_callback=_point_catcher_listener,
            ),
            name=f"Pandora CAS entry {entry.entry_id} changes listener",
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

    new_data = {**entry.data}
    new_options = {**entry.options}
    new_unique_id = UNDEFINED

    if entry.version < 3:
        for src in (new_data, new_options):
            for key in ("polling_interval", "user_agent"):
                if key in src:
                    del src[key]
        entry.version = 3

    if entry.version < 4:
        new_options.setdefault(CONF_VERIFY_SSL, True)
        new_options.setdefault(CONF_DISABLE_WEBSOCKETS, False)
        # new_unique_id = entry.unique_id or entry.data[CONF_USERNAME]
        entry.version = 4

    if entry.version < 5:
        account = PandoraOnlineAccount(
            username=new_data[CONF_USERNAME],
            password=new_data[CONF_PASSWORD],
            access_token=new_data.get(CONF_ACCESS_TOKEN),
            session=async_get_clientsession(
                hass, verify_ssl=new_options[CONF_VERIFY_SSL]
            ),
        )

        await async_authenticate_account(account, no_device_update=True)

        new_data[CONF_ACCESS_TOKEN] = account.access_token
        new_unique_id = str(account.user_id)

        entry.version = 5

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options=new_options,
        unique_id=new_unique_id,
    )

    _LOGGER.info(f"Upgraded configuration entry to version {entry.version}")

    return True
