"""Device triggers for Pandora Car Alarm system component."""

__all__ = ("TRIGGER_SCHEMA", "async_get_triggers", "async_attach_trigger")

import logging
from typing import Final

import voluptuous as vol
from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import (
    event as event_trigger,
)
from homeassistant.const import (
    CONF_TYPE,
    CONF_PLATFORM,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
)
from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from custom_components.pandora_cas import event_enum_to_type
from custom_components.pandora_cas.const import (
    EVENT_TYPE_EVENT,
    DOMAIN,
    CONF_EVENT_TYPE,
)
from pandora_cas.enums import PrimaryEventID

_LOGGER: Final = logging.getLogger(__name__)

TRIGGER_ID_MAPPING = {
    event_enum_to_type(e): e for e in PrimaryEventID if e != PrimaryEventID.UNKNOWN
}

TRIGGER_TYPES: Final = set(TRIGGER_ID_MAPPING)
TRIGGER_SCHEMA: Final = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)

DEVICE: Final = "device"


def async_get_pandora_id_by_device_id(
    hass: HomeAssistant, device_id: str
) -> int | None:
    if device := async_get_device_registry(hass).async_get(device_id):
        for identifier in device.identifiers:
            if len(identifier) != 2 or identifier[0] != DOMAIN:
                continue
            try:
                return int(identifier[1])
            except (TypeError, ValueError):
                continue


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for a Pandora CAS device."""

    # Find API device object by HA device ID
    if async_get_pandora_id_by_device_id(hass, device_id) is None:
        raise InvalidDeviceAutomationConfig(f"Not a {DOMAIN} device {device_id}")
    return [
        {
            CONF_PLATFORM: DEVICE,
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a Pandora CAS trigger."""

    if (
        pandora_id := async_get_pandora_id_by_device_id(
            hass, device_id := config[CONF_DEVICE_ID]
        )
    ) is None:
        raise InvalidDeviceAutomationConfig(f"Not a {DOMAIN} device {device_id}")

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_TYPE_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: pandora_id,
                CONF_EVENT_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass,
        event_config,
        action,
        trigger_info,
        platform_type=DEVICE,
    )
