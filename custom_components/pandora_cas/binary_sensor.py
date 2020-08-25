"""Binary sensor platform for Pandora Car Alarm System."""
__all__ = ["ENTITY_TYPES", "async_setup_entry"]

import logging
from functools import partial

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DOMAIN as PLATFORM_DOMAIN, BinarySensorEntity,
    ENTITY_ID_FORMAT
)
from homeassistant.const import ATTR_NAME, ATTR_ICON, ATTR_DEVICE_CLASS

from . import (
    ATTR_ATTRIBUTE,
    ATTR_STATE_SENSITIVE,
    ATTR_FLAG,
    ATTR_DEFAULT,
    PandoraCASBooleanEntity,
    async_platform_setup_entry,
)
from .api import BitStatus

_LOGGER = logging.getLogger(__name__)

_car_door_icons = ("mdi:car-door-lock", "mdi:car-door")
ENTITY_TYPES = {
    'connection_state': {
        ATTR_NAME: "Connection state",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
        ATTR_ATTRIBUTE: "is_online",
        ATTR_DEFAULT: True,
    },
    'moving': {
        ATTR_NAME: "Moving",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_MOTION,
        ATTR_STATE_SENSITIVE: True,
        ATTR_ATTRIBUTE: "is_moving",
    },

    # Status-related sensors
    'left_front_door': {
        ATTR_NAME: "Left Front Door",
        ATTR_ICON: _car_door_icons, ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.DOOR_FRONT_LEFT_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'right_front_door': {
        ATTR_NAME: "Right Front Door",
        ATTR_ICON: _car_door_icons, ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.DOOR_FRONT_RIGHT_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'left_back_door': {
        ATTR_NAME: "Left Back Door",
        ATTR_ICON: _car_door_icons, ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.DOOR_BACK_LEFT_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'right_back_door': {
        ATTR_NAME: "Right Back Door",
        ATTR_ICON: _car_door_icons, ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.DOOR_BACK_RIGHT_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'trunk': {
        ATTR_NAME: "Trunk",
        ATTR_ICON: "mdi:car-back", ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.TRUNK_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'hood': {
        ATTR_NAME: "Hood",
        ATTR_ICON: "mdi:car", ATTR_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.HOOD_OPEN,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    'parking': {
        ATTR_NAME: "Parking Mode",
        ATTR_ICON: "mdi:car-brake-parking",
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.HANDBRAKE_ENGAGED,
        ATTR_STATE_SENSITIVE: True,
    },
    'brakes': {
        ATTR_NAME: "Brakes",
        ATTR_ICON: "mdi:car-brake-hold",
        ATTR_ATTRIBUTE: "status", ATTR_FLAG: BitStatus.BRAKES_ENGAGED,
        ATTR_STATE_SENSITIVE: True,
    },
}


class PandoraCASBinarySensor(PandoraCASBooleanEntity, BinarySensorEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool:
        """Return current state of """
        return bool(self._state)


async_setup_entry = partial(async_platform_setup_entry, PLATFORM_DOMAIN, PandoraCASBinarySensor, logger=_LOGGER)
