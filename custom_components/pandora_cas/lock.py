"""Switch entity for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import dataclasses
import logging
from asyncio import run_coroutine_threadsafe
from dataclasses import dataclass
from functools import partial
from typing import Any, TYPE_CHECKING, Final

from homeassistant.components.lock import (
    LockEntity,
    ENTITY_ID_FORMAT,
    LockEntityDescription,
)

from custom_components.pandora_cas.const import CONF_FORCE_LOCK_ICONS
from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASBooleanEntityDescription,
    PandoraCASBooleanEntity,
)
from pandora_cas.device import PandoraOnlineDevice
from pandora_cas.enums import CommandID, BitStatus

if TYPE_CHECKING:
    from custom_components.pandora_cas import PandoraCASUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)


@dataclass
class PandoraCASLockEntityDescription(
    PandoraCASBooleanEntityDescription, LockEntityDescription
):
    icon_turning_on: str | None = None
    icon_turning_off: str | None = None


# noinspection PyArgumentList
ENTITY_TYPES = [
    PandoraCASLockEntityDescription(
        key="central_lock",
        name="Central Lock",
        online_sensitive=True,
        attribute="bit_state",
        flag=BitStatus.LOCKED,
        command_on=CommandID.LOCK,
        command_off=CommandID.UNLOCK,
    )
]


class PandoraCASLock(PandoraCASBooleanEntity, LockEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    def __init__(
        self,
        coordinator: "PandoraCASUpdateCoordinator",
        pandora_device: PandoraOnlineDevice,
        entity_description: "PandoraCASLockEntityDescription",
        *args,
        **kwargs,
    ) -> None:
        if coordinator.config_entry.options.get(CONF_FORCE_LOCK_ICONS):
            entity_description = dataclasses.replace(
                entity_description,
                icon_turning_on="mdi:lock-clock",
                icon_turning_off="mdi:lock-clock",
            )
        super().__init__(
            coordinator, pandora_device, entity_description, *args, **kwargs
        )

    @property
    def is_locked(self) -> bool | None:
        if not self.entity_description.assumed_state:
            return self._attr_native_value

    @property
    def is_locking(self) -> bool | None:
        return self._is_turning_on

    @property
    def is_unlocking(self) -> bool | None:
        return self._is_turning_off

    # @property
    # def is_jammed(self) -> bool | None:
    #     return self._last_command_failed
    #     return

    async def async_lock(self, **kwargs) -> None:
        await self.run_binary_command(True)

    async def async_unlock(self, **kwargs) -> None:
        await self.run_binary_command(False)

    def lock(self, **kwargs: Any) -> None:
        run_coroutine_threadsafe(self.async_lock(), self.hass.loop).result()

    def unlock(self, **kwargs: Any) -> None:
        run_coroutine_threadsafe(self.async_unlock(), self.hass.loop).result()

    def open(self, **kwargs):
        raise NotImplementedError("Not supported")


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASLock,
    logger=_LOGGER,
)
