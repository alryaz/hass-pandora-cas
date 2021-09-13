"""Switch entity for Pandora Car Alarm System."""
import logging
from asyncio import run_coroutine_threadsafe
from functools import partial
from typing import Any

from homeassistant.components.binary_sensor import DEVICE_CLASS_LOCK
from homeassistant.components.lock import (
    LockEntity,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import ATTR_NAME, ATTR_ICON, ATTR_DEVICE_CLASS, ATTR_COMMAND

from . import (
    ATTR_FLAG,
    ATTR_ATTRIBUTE,
    ATTR_STATE_SENSITIVE,
    ATTR_DEFAULT,
    PandoraCASBooleanEntity,
    async_platform_setup_entry,
)
from .api import BitStatus, CommandID

_LOGGER = logging.getLogger(__name__)

LOCK_TYPES = {
    "central_lock": {
        ATTR_NAME: "Central Lock",
        ATTR_ICON: ("mdi:lock-open", "mdi:lock"),
        ATTR_DEVICE_CLASS: DEVICE_CLASS_LOCK,
        ATTR_ATTRIBUTE: "status",
        ATTR_FLAG: BitStatus.LOCKED,
        ATTR_STATE_SENSITIVE: True,
        ATTR_COMMAND: (CommandID.UNLOCK, CommandID.LOCK),
        ATTR_DEFAULT: True,
    },
}


class PandoraCASLock(PandoraCASBooleanEntity, LockEntity):
    ENTITY_TYPES = LOCK_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    def lock(self, **kwargs):
        run_coroutine_threadsafe(self.async_lock(), self.hass.loop).result()

    def unlock(self, **kwargs: Any) -> None:
        run_coroutine_threadsafe(self.async_unlock(), self.hass.loop).result()

    def open(self, **kwargs):
        _LOGGER.error("Unlatching (`open`) is not supported.")
        return False

    @property
    def is_locked(self) -> bool:
        return bool(self._state)

    async def async_lock(self, **kwargs) -> None:
        await self._run_boolean_command(True)

    async def async_unlock(self, **kwargs) -> None:
        await self._run_boolean_command(False)


async_setup_entry = partial(
    async_platform_setup_entry, PLATFORM_DOMAIN, PandoraCASLock, logger=_LOGGER
)
