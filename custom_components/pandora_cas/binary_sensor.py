"""Binary sensor platform for Pandora Car Alarm System."""
__all__ = ["ENTITY_TYPES", "async_setup_entry"]

import logging
from functools import partial
from typing import Any, Dict

import attr
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DOMAIN as PLATFORM_DOMAIN,
    BinarySensorEntity,
    ENTITY_ID_FORMAT,
)
from homeassistant.const import ATTR_NAME, ATTR_ICON, ATTR_DEVICE_CLASS

from . import PandoraCASBooleanEntity, async_platform_setup_entry
from .api import BitStatus
from .const import *

_LOGGER = logging.getLogger(__name__)

_car_door_icons = ("mdi:car-door-lock", "mdi:car-door")
_car_glass_icons = ("mdi:car-windshield", "mdi:car-windshield-outline")

ENTITY_TYPES = {
    "connection_state": {
        ATTR_NAME: "Connection state",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
        ATTR_ATTRIBUTE: "is_online",
        ATTR_ATTRIBUTE_SOURCE: True,
    },
    "moving": {
        ATTR_NAME: "Moving",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_MOTION,
        ATTR_STATE_SENSITIVE: True,
        ATTR_ATTRIBUTE: "is_moving",
    },
    # Status-related sensors
    "left_front_door": {
        ATTR_NAME: "Left Front Door",
        ATTR_ICON: _car_door_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.DOOR_FRONT_LEFT_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "right_front_door": {
        ATTR_NAME: "Right Front Door",
        ATTR_ICON: _car_door_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.DOOR_FRONT_RIGHT_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "left_back_door": {
        ATTR_NAME: "Left Back Door",
        ATTR_ICON: _car_door_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.DOOR_BACK_LEFT_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "right_back_door": {
        ATTR_NAME: "Right Back Door",
        ATTR_ICON: _car_door_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.DOOR_BACK_RIGHT_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "left_front_glass": {
        ATTR_NAME: "Left Front Glass",
        ATTR_ICON: _car_glass_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "can_glass_front_left",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_front_glass": {
        ATTR_NAME: "Right Front Glass",
        ATTR_ICON: _car_glass_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "can_glass_front_right",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "left_back_glass": {
        ATTR_NAME: "Left Back Glass",
        ATTR_ICON: _car_glass_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "can_glass_back_left",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_back_glass": {
        ATTR_NAME: "Right Back Glass",
        ATTR_ICON: _car_glass_icons,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "can_glass_back_right",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "trunk": {
        ATTR_NAME: "Trunk",
        ATTR_ICON: "mdi:car-back",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.TRUNK_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "hood": {
        ATTR_NAME: "Hood",
        ATTR_ICON: "mdi:car",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.HOOD_OPEN,
        ATTR_STATE_SENSITIVE: True,
    },
    "parking": {
        ATTR_NAME: "Parking Mode",
        ATTR_ICON: "mdi:car-brake-parking",
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.HANDBRAKE_ENGAGED,
        ATTR_STATE_SENSITIVE: True,
    },
    "brakes": {
        ATTR_NAME: "Brakes",
        ATTR_ICON: "mdi:car-brake-hold",
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.BRAKES_ENGAGED,
        ATTR_STATE_SENSITIVE: True,
    },
    "ignition": {
        ATTR_NAME: "Ignition",
        ATTR_ICON: "mdi:key-variant",
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.IGNITION,
    },
    "exterior_lights": {
        ATTR_NAME: "Exterior Lights",
        ATTR_ICON: "mdi:car-light-high",
        ATTR_ATTRIBUTE: "bit_state",
        ATTR_FLAG: BitStatus.EXTERIOR_LIGHTS_ACTIVE,
    },
    "ev_charging_connected": {
        ATTR_NAME: "EV Charging Connected",
        ATTR_ICON: "mdi:ev-station",
        ATTR_ATTRIBUTE: "ev_charging_connected",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
}


class PandoraCASBinarySensor(PandoraCASBooleanEntity, BinarySensorEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool:
        """Return current state of"""
        return bool(self._state)

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        existing_attributes = super().device_state_attributes
        entity_type = self._entity_type

        if entity_type == "connection_state":
            state = self._device.state
            if state is not None:
                existing_attributes.update(attr.asdict(state, True))

        elif entity_type == "ev_charging_connected":
            if not self._device.is_online:
                return existing_attributes

            state = self._device.state

            existing_attributes["slow_charging"] = state.ev_charging_slow
            existing_attributes["fast_charging"] = state.ev_charging_fast
            existing_attributes["ready_status"] = state.ev_status_ready

        return existing_attributes


async_setup_entry = partial(
    async_platform_setup_entry,
    PLATFORM_DOMAIN,
    PandoraCASBinarySensor,
    logger=_LOGGER,
)
