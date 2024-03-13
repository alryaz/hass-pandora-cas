"""Binary sensor platform for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import asyncio
import logging
from functools import partial
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    ENTITY_ID_FORMAT,
    SwitchEntityDescription,
)

from custom_components.pandora_cas.const import CONF_ENGINE_STATE_BY_RPM
from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASBooleanEntityDescription,
    PandoraCASBooleanEntity,
    has_device_type,
)
from pandora_cas.data import CurrentState
from pandora_cas.enums import PandoraDeviceTypes, CommandID, BitStatus, Features

_LOGGER = logging.getLogger(__name__)


class PandoraCASSwitchEntityDescription(
    PandoraCASBooleanEntityDescription, SwitchEntityDescription
):
    """Switch entity description for Pandora"""


# noinspection PyArgumentList
ENTITY_TYPES = [
    PandoraCASSwitchEntityDescription(
        key="active_security",
        name="Active Security",
        icon="mdi:shield-car",
        icon_off="mdi:shield-off",
        icon_turning_on="mdi:shield-sync",
        attribute=CurrentState.bit_state,
        flag=BitStatus.ACTIVE_SECURITY_ENABLED,
        command_on=CommandID.ENABLE_ACTIVE_SECURITY,
        command_off=CommandID.DISABLE_ACTIVE_SECURITY,
        features=Features.ACTIVE_SECURITY,
    ),
    PandoraCASSwitchEntityDescription(
        key="tracking",
        name="Tracking",
        icon="mdi:map-marker-path",
        icon_off="mdi:map-marker-off",
        icon_turning_on="mdi:map-marker-plus",
        icon_turning_off="mdi:map-marker-minus",
        attribute=CurrentState.bit_state,
        flag=BitStatus.TRACKING_ENABLED,
        command_on=CommandID.ENABLE_TRACKING,
        command_off=CommandID.DISABLE_TRACKING,
        features=Features.TRACKING,
    ),
    PandoraCASSwitchEntityDescription(
        key="block_heater",
        name="Block Heater",
        icon="mdi:radiator-disabled",
        icon_on="mdi:radiator",
        icon_off="mdi:radiator-off",
        attribute=CurrentState.bit_state,
        flag=BitStatus.BLOCK_HEATER_ACTIVE,
        command_on=[
            (
                has_device_type(PandoraDeviceTypes.NAV12),
                CommandID.NAV12_TURN_ON_BLOCK_HEATER,
            ),
            (None, CommandID.TURN_ON_BLOCK_HEATER),
        ],
        command_off=[
            (
                has_device_type(PandoraDeviceTypes.NAV12),
                CommandID.NAV12_TURN_OFF_BLOCK_HEATER,
            ),
            (None, CommandID.TURN_OFF_BLOCK_HEATER),
        ],
        features=Features.HEATER,
    ),
    PandoraCASSwitchEntityDescription(
        key="engine",
        name="Engine",
        icon_off="mdi:engine-off",
        icon="mdi:engine",
        attribute=CurrentState.bit_state,
        flag=BitStatus.ENGINE_RUNNING,
        command_on=CommandID.START_ENGINE,
        command_off=CommandID.STOP_ENGINE,
        force_update_method_call=True,
        # features=Features.AUTO_START,  # @TODO: check whether true
    ),
    PandoraCASSwitchEntityDescription(
        key="service_mode",
        name="Service Mode",
        icon="mdi:progress-wrench",
        icon_off="mdi:wrench",
        attribute=CurrentState.bit_state,
        flag=BitStatus.SERVICE_MODE_ACTIVE,
        command_on=[
            (
                has_device_type(PandoraDeviceTypes.NAV12),
                CommandID.NAV12_ENABLE_SERVICE_MODE,
            ),
            (None, CommandID.ENABLE_SERVICE_MODE),
        ],
        command_off=[
            (has_device_type(PandoraDeviceTypes.NAV12), CommandID.DISABLE_SERVICE_MODE),
            (None, CommandID.DISABLE_SERVICE_MODE),
        ],
    ),
    PandoraCASSwitchEntityDescription(
        key="ext_channel",
        name="Extra Channel",
        icon="mdi:export",
        # attribute=CurrentState.bit_state,
        command_on=CommandID.TURN_ON_EXT_CHANNEL,
        command_off=CommandID.TURN_OFF_EXT_CHANNEL,
        features=Features.CHANNEL,
        assumed_state=True,
    ),
    PandoraCASSwitchEntityDescription(
        key="status_output",
        name="Status Output",
        icon="mdi:led-off",
        # icon_turning_on="",
        # icon_turning_off="",
        command_on=[
            (
                has_device_type(PandoraDeviceTypes.NAV12),
                CommandID.NAV12_ENABLE_STATUS_OUTPUT,
            ),
            (None, CommandID.ENABLE_STATUS_OUTPUT),
        ],
        command_off=[
            (
                has_device_type(PandoraDeviceTypes.NAV12),
                CommandID.NAV12_DISABLE_STATUS_OUTPUT,
            ),
            (None, CommandID.DISABLE_STATUS_OUTPUT),
        ],
        assumed_state=True,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_glass_heating",
        name="Climate Glass Heating",
        icon="mdi:mirror",
        attribute=CurrentState.can_climate_glass_heat,
        command_on=CommandID.CLIMATE_GLASS_HEAT_TURN_ON,
        command_off=CommandID.CLIMATE_GLASS_HEAT_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_steering_heating",
        name="Climate Steering Heating",
        icon="mdi:steering",
        icon_off="mdi:steering-off",
        attribute=CurrentState.can_climate_steering_heat,
        command_on=CommandID.CLIMATE_STEERING_HEAT_TURN_ON,
        command_off=CommandID.CLIMATE_STEERING_HEAT_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_air_conditioning",
        name="Climate Air Conditioning",
        icon="mdi:air-conditioner",
        icon_off="mdi:fan-off",
        attribute=CurrentState.can_climate_ac,
        command_on=CommandID.CLIMATE_AC_TURN_ON,
        command_off=CommandID.CLIMATE_AC_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_system",
        name="Climate System",
        icon="mdi:hvac",
        icon_off="mdi:hvac-off",
        attribute=CurrentState.can_climate,
        command_on=CommandID.CLIMATE_SYS_TURN_ON,
        command_off=CommandID.CLIMATE_SYS_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_defroster",
        name="Climate Defroster",
        icon="mdi:car-defrost-front",
        icon_off="mdi:car-windshield-outline",
        attribute=CurrentState.can_climate_defroster,
        command_on=CommandID.CLIMATE_DEFROSTER_TURN_ON,
        command_off=CommandID.CLIMATE_DEFROSTER_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSwitchEntityDescription(
        key="climate_battery_heating",
        name="Climate Battery Heating",
        icon="mdi:car-battery",
        attribute=CurrentState.battery_warm_up,
        command_on=CommandID.CLIMATE_BATTERY_HEAT_TURN_ON,
        command_off=CommandID.CLIMATE_BATTERY_HEAT_TURN_OFF,
        entity_registry_enabled_default=False,
    ),
]


class PandoraCASSwitch(PandoraCASBooleanEntity, SwitchEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    entity_description: PandoraCASSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        if not self.entity_description.assumed_state:
            return self._attr_native_value

    async def async_turn_on(self, **kwargs) -> None:
        """Proxy method to run enable boolean command."""
        await self.run_binary_command(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Proxy method to run disable boolean command."""
        await self.run_binary_command(False)

    def turn_on(self, **kwargs: Any) -> None:
        """Compatibility for synchronous turn on calls."""
        asyncio.run_coroutine_threadsafe(self.async_turn_on(), self.hass.loop).result()

    def turn_off(self, **kwargs: Any) -> None:
        """Compatibility for synchronous turn off calls."""
        asyncio.run_coroutine_threadsafe(self.async_turn_off(), self.hass.loop).result()

    def get_native_value(self) -> Any | None:
        if (
            self.entity_description.key == "engine"
            and self._device_config[CONF_ENGINE_STATE_BY_RPM]
        ):
            if (current_rpm := self.pandora_device.state.engine_rpm) is not None:
                return current_rpm > 0
        return super().get_native_value()


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASSwitch,
    logger=_LOGGER,
)
