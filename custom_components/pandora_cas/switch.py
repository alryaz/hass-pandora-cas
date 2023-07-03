"""Binary sensor platform for Pandora Car Alarm System."""
__all__ = ("ENTITY_TYPES", "async_setup_entry")

import asyncio
import logging
from functools import partial
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity, ENTITY_ID_FORMAT

from custom_components.pandora_cas import CONF_ENGINE_STATE_BY_RPM
from custom_components.pandora_cas.api import (
    BitStatus,
    CommandID,
    Features,
    PandoraDeviceTypes,
)
from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASBooleanEntityDescription,
    PandoraCASBooleanEntity,
)

_LOGGER = logging.getLogger(__name__)


ENTITY_TYPES = [
    PandoraCASBooleanEntityDescription(
        key="active_security",
        name="Active Security",
        icon="mdi:shield-car",
        icon_off="mdi:shield-off",
        icon_turning_on="mdi:shield-sync",
        attribute="bit_state",
        flag=BitStatus.ACTIVE_SECURITY_ENABLED,
        command_on=CommandID.ENABLE_ACTIVE_SECURITY,
        command_off=CommandID.DISABLE_ACTIVE_SECURITY,
        features=Features.ACTIVE_SECURITY,
    ),
    PandoraCASBooleanEntityDescription(
        key="tracking",
        name="Tracking",
        icon="mdi:map-marker-path",
        icon_off="mdi:map-marker-off",
        icon_turning_on="mdi:map-marker-plus",
        icon_turning_off="mdi:map-marker-minus",
        attribute="bit_state",
        flag=BitStatus.TRACKING_ENABLED,
        command_on=CommandID.ENABLE_TRACKING,
        command_off=CommandID.DISABLE_TRACKING,
        features=Features.TRACKING,
    ),
    PandoraCASBooleanEntityDescription(
        key="block_heater",
        name="Block Heater",
        icon="mdi:radiator-disabled",
        icon_on="mdi:radiator",
        icon_off="mdi:radiator-off",
        attribute="bit_state",
        flag=BitStatus.BLOCK_HEATER_ACTIVE,
        command_on={
            None: CommandID.TURN_ON_BLOCK_HEATER,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_TURN_ON_BLOCK_HEATER,
        },
        command_off={
            None: CommandID.TURN_OFF_BLOCK_HEATER,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_TURN_OFF_BLOCK_HEATER,
        },
        features=Features.BLOCK_HEATER,
    ),
    PandoraCASBooleanEntityDescription(
        key="engine",
        name="Engine",
        icon_off="mdi:engine-off",
        icon="mdi:engine",
        attribute="bit_state",
        flag=BitStatus.ENGINE_RUNNING,
        command_on=CommandID.START_ENGINE,
        command_off=CommandID.STOP_ENGINE,
        force_update_method_call=True,
        # features=Features.AUTO_START,  # @TODO: check whether true
    ),
    PandoraCASBooleanEntityDescription(
        key="service_mode",
        name="Service Mode",
        icon_off="mdi:wrench",
        attribute="bit_state",
        flag=BitStatus.SERVICE_MODE_ACTIVE,
        command_on={
            None: CommandID.ENABLE_SERVICE_MODE,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_ENABLE_SERVICE_MODE,
        },
        command_off={
            None: CommandID.DISABLE_SERVICE_MODE,
            PandoraDeviceTypes.NAV12: CommandID.DISABLE_SERVICE_MODE,
        },
    ),
    PandoraCASBooleanEntityDescription(
        key="ext_channel",
        name="Extra Channel",
        icon="mdi:export",
        attribute="bit_state",
        command_on=CommandID.TURN_ON_EXT_CHANNEL,
        command_off=CommandID.TURN_OFF_EXT_CHANNEL,
        features=Features.EXT_CHANNEL,
        assumed_state=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="status_output",
        name="Status Output",
        icon="mdi:led-off",
        # icon_turning_on="",
        # icon_turning_off="",
        command_on={
            None: CommandID.ENABLE_STATUS_OUTPUT,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_ENABLE_STATUS_OUTPUT,
        },
        command_off={
            None: CommandID.DISABLE_STATUS_OUTPUT,
            PandoraDeviceTypes.NAV12: CommandID.NAV12_DISABLE_STATUS_OUTPUT,
        },
        assumed_state=True,
    ),
]


class PandoraCASSwitch(PandoraCASBooleanEntity, SwitchEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

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
        asyncio.run_coroutine_threadsafe(
            self.async_turn_on(), self.hass.loop
        ).result()

    def turn_off(self, **kwargs: Any) -> None:
        """Compatibility for synchronous turn off calls."""
        asyncio.run_coroutine_threadsafe(
            self.async_turn_off(), self.hass.loop
        ).result()

    def get_native_value(self) -> Optional[Any]:
        if (
            self.entity_description.key == "engine"
            and self._device_config[CONF_ENGINE_STATE_BY_RPM]
        ):
            if (
                current_rpm := self.pandora_device.state.engine_rpm
            ) is not None:
                return current_rpm > 0
        return super().get_native_value()


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASSwitch,
    logger=_LOGGER,
)
