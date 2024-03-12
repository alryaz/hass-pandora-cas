"""Number platform for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from asyncio import run_coroutine_threadsafe
from dataclasses import dataclass
from functools import partial
from typing import Final, Callable, Any, TypeVar

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    NumberDeviceClass,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from custom_components.pandora_cas.entity import (
    PandoraCASEntity,
    async_platform_setup_entry,
    PandoraCASEntityDescription,
    CommandOptions,
)
from pandora_cas.data import CurrentState
from pandora_cas.enums import CommandParams, CommandID

_LOGGER: Final = logging.getLogger(__name__)


@dataclass
class PandoraCASNumberEntityDescription(
    PandoraCASEntityDescription, NumberEntityDescription
):
    parameter: str | None = None
    converter: Callable[[float], Any] | None = None
    icon_setting: str | None = "mdi:progress-clock"
    icon_min: str | None = None
    command_set: CommandOptions | None = None
    command_init: CommandOptions | None = None
    incremental: bool | None = None


# noinspection PyArgumentList
ENTITY_TYPES: list[PandoraCASNumberEntityDescription] = [
    PandoraCASNumberEntityDescription(
        key="climate_target_temperature",
        name="Climate Target Temperature",
        icon="mdi:thermometer",
        attribute=CurrentState.can_climate_temperature,
        command_set=CommandID.CLIMATE_SET_TEMPERATURE,
        parameter=CommandParams.CLIMATE_TEMP,
        converter=int,
        native_min_value=0,
        native_max_value=80,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.SLIDER,
        entity_registry_enabled_default=False,
    ),
    PandoraCASNumberEntityDescription(
        key="climate_seat_heating",
        name="Climate Seat Heating",
        icon="mdi:car-seat-heater",
        icon_min="mdi:car-seat",
        command_set=CommandID.CLIMATE_SEAT_HEAT_TURN_ON,
        command_init=CommandID.CLIMATE_SEAT_HEAT_TURN_OFF,
        attribute=CurrentState.can_climate_seat_heat_level,
        incremental=False,
        native_min_value=0,
        native_max_value=0,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_registry_enabled_default=False,
    ),
    PandoraCASNumberEntityDescription(
        key="climate_seat_ventilation",
        name="Climate Seat Ventilation",
        icon="mdi:car-seat-cooler",
        icon_min="mdi:car-seat",
        command_set=CommandID.CLIMATE_SEAT_VENT_TURN_ON,
        command_init=CommandID.CLIMATE_SEAT_VENT_TURN_OFF,
        attribute=CurrentState.can_climate_seat_vent_level,
        incremental=False,
        native_min_value=0,
        native_max_value=0,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_registry_enabled_default=False,
    ),
]

_TCmdStep = TypeVar("_TCmdStep")
_TCmdInit = TypeVar("_TCmdInit")


def calculate_incremental_sequence(
    current: int | float | None,
    target: int | float,
    minimum: int | float,
    maximum: int | float,
    step: int | float,
    cmd_step: _TCmdStep,
    cmd_init: _TCmdInit | None = None,
    incremental: bool = True,
) -> list[_TCmdStep | _TCmdInit]:
    if current is None and cmd_init is None:
        raise ValueError("current and cmd_init cannot be None at the same time")

    commands = []

    if (current is None) or (cmd_init is not None and incremental and current < target):
        commands.append(cmd_init)
        current = minimum

    while current != target:
        commands.append(cmd_step)
        if (not incremental) and (current == minimum):
            current = maximum
        elif incremental and (current == maximum):
            current = minimum
        elif incremental:
            current += step
        else:
            current -= step

    return commands


class PandoraCASNumber(PandoraCASEntity, NumberEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    entity_description: PandoraCASNumberEntityDescription

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._is_setting = False

    @property
    def icon(self) -> str | None:
        if self.available:
            e = self.entity_description
            if (i := e.icon_setting) and self._is_setting:
                return i
            if (i := e.icon_min) and (
                self.native_value == self.entity_description.min_value
            ):
                return i
        return super().icon

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        run_coroutine_threadsafe(
            self.async_set_native_value(value), self.hass.loop
        ).result()

    @callback
    def reset_command_event(self) -> None:
        self._is_setting = False
        super().reset_command_event()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if (command_set := self.entity_description.command_set) is None:
            raise HomeAssistantError("set command unavailable")

        incremental = self.entity_description.incremental
        parameter = self.entity_description.parameter
        if not (incremental is None or parameter is None):
            raise HomeAssistantError("parameters cannot be passed for sequence calls")

        coroutine = None
        if incremental is None:
            if (param := self.entity_description.parameter) is None:
                param = self.entity_description.attribute
            if (converter := self.entity_description.converter) is not None:
                value = converter(value)
            coroutine = self.run_device_command(command_set, {param: value})
        else:
            commands = calculate_incremental_sequence(
                self.native_value,
                value,
                self.entity_description.min_value,
                self.entity_description.max_value,
                self.entity_description.step,
                command_set,
                self.entity_description.command_init,
                incremental,
            )
            if commands:
                coroutine = self.run_device_command_sequence(commands)

        if coroutine is not None:
            self._is_setting = True
            await coroutine


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASNumber,
    logger=_LOGGER,
)
