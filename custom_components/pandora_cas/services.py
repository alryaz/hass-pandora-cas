"""Pandora Car Alarm system services loaders."""

__all__ = (
    "SERVICE_PREDEFINED_COMMAND_SCHEMA",
    "SERVICE_REMOTE_COMMAND",
    "SERVICE_REMOTE_COMMAND_SCHEMA",
    "async_execute_remote_command",
    "async_find_device_object",
    "async_get_pandora_id_by_device_id",
    "async_register_services",
    "determine_command_by_slug",
    "iterate_commands_to_register",
)

import asyncio
import logging
from functools import partial
from typing import Mapping, Any, Final

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.util import slugify

from custom_components.pandora_cas.const import (
    ATTR_COMMAND_ID,
    DOMAIN,
    ATTR_ENSURE_COMPLETE,
)
from pandora_cas.device import PandoraOnlineDevice
from pandora_cas.enums import CommandID

_LOGGER: Final = logging.getLogger(__name__)


def determine_command_by_slug(command_slug: str) -> int:
    """
    Determine command by its slug value.
    :param command_slug: Command slug identifier.
    :raises vol.Invalid: Invalid slug value provided.
    :return: Command identifier.
    """
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
            vol.Optional(ATTR_ENSURE_COMPLETE, default=False): cv.boolean,
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
                vol.All(cv.string, determine_command_by_slug),
            ),
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


def iterate_commands_to_register(cls=CommandID):
    for key, value in cls.__members__.items():
        yield slugify(key.lower()), value.value


@callback
def async_get_pandora_id_by_device_id(
    hass: HomeAssistant, device_id: str | int
) -> int | None:
    """
    Find a PandoraOnlineDevice object amongst loaded configuration entries.
    :param hass: Home Assistant object.
    :param device_id: Numeric pandora identifier
    :return: (PandoraOnlineDevice object) OR (None if not found)
    """
    try:
        return int(device_id)
    except (TypeError, ValueError):
        if not (device := async_get_device_registry(hass).async_get(device_id)):
            return
        for identifier in device.identifiers:
            if len(identifier) != 2 or identifier[0] != DOMAIN:
                continue
            try:
                return int(identifier[1])
            except (TypeError, ValueError):
                continue


@callback
def async_find_device_object(
    hass: HomeAssistant, device_id: int
) -> PandoraOnlineDevice | None:
    """
    Find a PandoraOnlineDevice object amongst loaded configuration entries.
    :param hass: Home Assistant object.
    :param device_id: Numeric pandora identifier
    :return: (PandoraOnlineDevice object) OR (None if not found)
    """
    for config_entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        try:
            return coordinator.account.devices[device_id]
        except KeyError:
            continue


async def async_execute_remote_command(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    command_id: int | CommandID | None = None,
    params: Mapping[str, Any] | None = None,
) -> None:
    """
    Handle service calls.
    :param hass: Home Assistant object.
    :param call: Service call object.
    :param command_id: Predefined command identifier (optional)
    :param params: Predefined command parameters (optional)
    :return: None
    """
    command_params = dict(call.data)
    _LOGGER.debug(f"Called service '{call.service}' with data: {command_params}")

    # command_id may be provided externally using partial(...)
    if command_id is None:
        command_id = command_params.pop(ATTR_COMMAND_ID)
    elif command_id != command_params.pop(ATTR_COMMAND_ID, command_id):
        raise HomeAssistantError("Command ID cannot be overridden in calls")

    # determine device identifier
    param_device_id = command_params.pop(ATTR_DEVICE_ID)
    device_id = async_get_pandora_id_by_device_id(hass, param_device_id)
    if device_id is None:
        raise HomeAssistantError(f"Invalid device ID '{param_device_id}' provided")

    # find device matching identifier
    device = async_find_device_object(hass, device_id)
    if device is None:
        raise HomeAssistantError(f"Device with ID '{device_id}' not found.")

    # Pop ensure complete before merging predefined parameters
    ensure_complete = command_params.pop(ATTR_ENSURE_COMPLETE, False)

    # merge predefined parameters
    if params:
        command_params.update(params)

    # execute remote command
    result = device.async_remote_command(
        command_id, command_params, ensure_complete=ensure_complete
    )
    if asyncio.iscoroutine(result):
        await result


async def async_register_services(hass: HomeAssistant) -> None:
    # register the remote services
    _register_service = hass.services.async_register

    _register_service(
        DOMAIN,
        SERVICE_REMOTE_COMMAND,
        partial(async_execute_remote_command, hass),
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
                async_execute_remote_command,
                hass,
                command_id=command_id,
            ),
            schema=SERVICE_PREDEFINED_COMMAND_SCHEMA,
        )
