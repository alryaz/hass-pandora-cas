"""Binary sensor platform for Pandora Car Alarm System."""
__all__ = ["ENTITY_TYPES", "async_setup_entry"]

import logging
from asyncio import run_coroutine_threadsafe
from functools import partial
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import ATTR_NAME, ATTR_ICON, ATTR_COMMAND

from . import (
    ATTR_FLAG,
    ATTR_ATTRIBUTE,
    ATTR_STATE_SENSITIVE,
    ATTR_FEATURE,
    ATTR_DEFAULT,
    PandoraCASBooleanEntity,
    async_platform_setup_entry,
)
from .api import BitStatus, CommandID, Features

_LOGGER = logging.getLogger(__name__)


ENTITY_TYPES = {
    "active_security": {
        ATTR_NAME: "Active Security",
        ATTR_ICON: ("mdi:shield-off", "mdi:shield-car"),
        ATTR_ATTRIBUTE: "status",
        ATTR_FLAG: BitStatus.ACTIVE_SECURITY,
        ATTR_STATE_SENSITIVE: True,
        ATTR_COMMAND: (
            CommandID.DISABLE_ACTIVE_SECURITY,
            CommandID.ENABLE_ACTIVE_SECURITY,
        ),
        ATTR_FEATURE: Features.ACTIVE_SECURITY,
        ATTR_DEFAULT: True,
    },
    "tracking": {
        ATTR_NAME: "Tracking",
        ATTR_ICON: ("mdi:map-marker-off", "mdi:map-marker-distance"),
        ATTR_ATTRIBUTE: "status",
        ATTR_FLAG: BitStatus.TRACKING_ENABLED,
        ATTR_STATE_SENSITIVE: True,
        ATTR_COMMAND: (CommandID.DISABLE_TRACKING, CommandID.ENABLE_TRACKING),
        ATTR_FEATURE: Features.TRACKING,
    },
    "coolant_heater": {
        ATTR_NAME: "Coolant Heater",
        ATTR_ICON: ("mdi:radiator-disabled", "mdi:radiator"),
        ATTR_ATTRIBUTE: "status",
        ATTR_FLAG: BitStatus.BLOCK_HEATER_ACTIVE,
        ATTR_STATE_SENSITIVE: True,
        ATTR_COMMAND: (
            CommandID.TURN_OFF_COOLANT_HEATER,
            CommandID.TURN_ON_COOLANT_HEATER,
        ),
        ATTR_FEATURE: Features.COOLANT_HEATER,
        ATTR_DEFAULT: True,
    },
    # 'ext_channel': {
    #     ATTR_NAME: "Extra Channel",
    #     ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.COOLANT_HEATER,
    #     ATTR_STATE_SENSITIVE: True,
    #     ATTR_COMMAND: (CommandID.TURN_OFF_EXT_CHANNEL, CommandID.TURN_ON_COOLANT_HEATER),
    #     ATTR_FEATURE: Features.EXT_CHANNEL,
    # },
    "engine": {
        ATTR_NAME: "Engine",
        ATTR_ICON: ("mdi:fan-off", "mdi:fan"),
        ATTR_ATTRIBUTE: "status",
        ATTR_FLAG: BitStatus.ENGINE_RUNNING,
        ATTR_STATE_SENSITIVE: True,
        ATTR_COMMAND: (CommandID.STOP_ENGINE, CommandID.START_ENGINE),
        ATTR_DEFAULT: True,
    },
    "service_mode": {
        ATTR_NAME: "Service Mode",
        ATTR_ICON: "mdi:wrench",
        ATTR_COMMAND: (CommandID.DISABLE_SERVICE_MODE, CommandID.ENABLE_SERVICE_MODE),
    },
    "ext_channel": {
        ATTR_NAME: "Extra Channel",
        ATTR_ICON: "mdi:export",
        ATTR_FEATURE: Features.EXT_CHANNEL,
        ATTR_COMMAND: (CommandID.TURN_OFF_EXT_CHANNEL, CommandID.TURN_ON_EXT_CHANNEL),
    },
}


class PandoraCASSwitch(PandoraCASBooleanEntity, SwitchEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool:
        """Return current state of switch."""
        return bool(self._state)

    @property
    def assumed_state(self) -> bool:
        """Missing attribute implies unable to access exact state."""
        return ATTR_ATTRIBUTE not in self._entity_config

    async def async_turn_on(self, **kwargs) -> None:
        """Proxy method to run enable boolean command."""
        await self._run_boolean_command(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Proxy method to run disable boolean command."""
        await self._run_boolean_command(False)

    def turn_on(self, **kwargs: Any) -> None:
        """Compatibility for synchronous turn on calls."""
        run_coroutine_threadsafe(self.async_turn_on(), self.hass.loop).result()

    def turn_off(self, **kwargs: Any) -> None:
        """Compatibility for synchronous turn off calls."""
        run_coroutine_threadsafe(self.async_turn_off(), self.hass.loop).result()


async_setup_entry = partial(
    async_platform_setup_entry, PLATFORM_DOMAIN, PandoraCASSwitch, logger=_LOGGER
)
