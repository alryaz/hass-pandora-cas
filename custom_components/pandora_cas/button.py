"""Button platform for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from typing import Callable, Final

from homeassistant.components.button import (
    ButtonEntity,
    ENTITY_ID_FORMAT,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASEntity,
    PandoraCASEntityDescription,
    CommandOptions,
    parse_description_command_id,
)
from pandora_cas.device import PandoraOnlineDevice
from pandora_cas.enums import PandoraDeviceTypes, CommandID

_LOGGER: Final = logging.getLogger(__name__)


@dataclass
class PandoraCASButtonEntityDescription(
    PandoraCASEntityDescription, ButtonEntityDescription
):
    command: CommandOptions | None = None
    icon_pressing: str | None = "mdi:progress-clock"
    allow_simultaneous_presses: bool = True


# noinspection PyArgumentList
ENTITY_TYPES = [
    PandoraCASButtonEntityDescription(
        key="erase_errors",
        name="Erase Errors",
        command={
            None: CommandID.ERASE_DTC,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_RESET_ERRORS,
        },
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:eraser",
    ),
    PandoraCASButtonEntityDescription(
        key="read_errors",
        name="Read Errors",
        command=CommandID.READ_DTC,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:barcode-scan",
    ),
    PandoraCASButtonEntityDescription(
        key="trigger_horn",
        name="Trigger Horn",
        command=CommandID.TRIGGER_HORN,
        icon="mdi:bugle",
    ),
    PandoraCASButtonEntityDescription(
        key="trigger_light",
        name="Trigger Light",
        command=CommandID.TRIGGER_LIGHT,
        icon="mdi:car-light-high",
    ),
    PandoraCASButtonEntityDescription(
        key="trigger_trunk",
        name="Trigger Trunk",
        command=CommandID.TRIGGER_TRUNK,
        icon="mdi:open-in-app",
    ),
    PandoraCASButtonEntityDescription(
        key="check",
        name="Check",
        command=CommandID.CHECK,
        icon="mdi:refresh",
    ),
    PandoraCASButtonEntityDescription(
        key="additional_command_1",
        name="Additional Command 1",
        command=CommandID.ADDITIONAL_COMMAND_1,
        icon="mdi:numeric-1-box",
    ),
    PandoraCASButtonEntityDescription(
        key="additional_command_2",
        name="Additional Command 2",
        command=CommandID.ADDITIONAL_COMMAND_2,
        icon="mdi:numeric-2-box",
    ),
    PandoraCASButtonEntityDescription(
        key="wake_up",
        name="Wake Up",
        icon="mdi:power-cycle",
        command=PandoraOnlineDevice.async_wake_up,
        online_sensitive=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        allow_simultaneous_presses=False,
    ),
    PandoraCASButtonEntityDescription(
        key="climate_comfort",
        name="Climate Comfort",
        icon="mdi:palm-tree",
        command=CommandID.CLIMATE_MODE_COMFORT,
    ),
    PandoraCASButtonEntityDescription(
        key="climate_interior_ventilation",
        name="Climate Interior Ventilation",
        icon="mdi:fan",
        command=CommandID.CLIMATE_MODE_VENT,
    ),
]


class PandoraCASButton(PandoraCASEntity, ButtonEntity):
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT
    ENTITY_TYPES = ENTITY_TYPES

    entity_description: PandoraCASButtonEntityDescription

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._is_pressing: bool = False
        self._command_waiter: Callable[[], ...] | None = None
        self._command_press_listener: Callable[[], ...] | None = None

    @property
    def icon(self) -> str | None:
        e = self.entity_description
        if not self.available:
            return e.icon
        if (i := e.icon_pressing) and self._is_pressing:
            return i
        return e.icon

    @callback
    def reset_command_event(self) -> None:
        self._is_pressing = False
        super().reset_command_event()

    async def async_press(self) -> None:
        """Proxy method to run disable boolean command."""
        if self._is_pressing and not self.entity_description.allow_simultaneous_presses:
            raise HomeAssistantError(
                "Simultaneous commands not allowed, wait until command completes"
            )
        command_id = parse_description_command_id(
            self.entity_description.command, self.pandora_device.type
        )
        self._is_pressing = True
        await self.run_device_command(command_id)

    def press(self) -> None:
        """Compatibility for synchronous turn on calls."""
        asyncio.run_coroutine_threadsafe(self.async_press(), self.hass.loop).result()

    def update_native_value(self) -> bool:
        """Native value for this entity type does not get updated.

        Therefore, an overriding placeholder is required to
        not do anything at all and not to trigger availability
        issues."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._add_command_listener(self.entity_description.command)


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASButton,
    logger=_LOGGER,
)
