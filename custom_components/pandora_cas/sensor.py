"""Sensor platform for Pandora Car Alarm System."""
__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from functools import partial
from typing import Optional, Union

from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN, ENTITY_ID_FORMAT
from homeassistant.const import (
    LENGTH_KILOMETERS,
    TEMP_CELSIUS,
    ATTR_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    SPEED_KILOMETERS_PER_HOUR,
)

from . import PandoraCASEntity, async_platform_setup_entry
from .const import *

try:
    from homeassistant.const import VOLT as ELECTRIC_POTENTIAL_VOLT
except ImportError:
    from homeassistant.const import ELECTRIC_POTENTIAL_VOLT

_LOGGER = logging.getLogger(__name__)


ENTITY_TYPES = {
    "mileage": {
        ATTR_NAME: "Mileage",
        ATTR_ICON: "mdi:map-marker-distance",
        ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
        ATTR_ATTRIBUTE: "mileage",
        ATTR_STATE_SENSITIVE: True,
        ATTR_FORMATTER: lambda v: round(float(v), 2),
        ATTR_ADDITIONAL_ATTRIBUTES: {},
        ATTR_DEFAULT: True,
    },
    "fuel": {
        ATTR_NAME: "Fuel Level",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ATTRIBUTE: "fuel",
        ATTR_STATE_SENSITIVE: False,
        ATTR_DEFAULT: True,
    },
    "interior_temperature": {
        ATTR_NAME: "Interior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ATTRIBUTE: "interior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "engine_temperature": {
        ATTR_NAME: "Engine Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ATTRIBUTE: "engine_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "exterior_temperature": {
        ATTR_NAME: "Exterior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ATTRIBUTE: "exterior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "balance": {
        ATTR_NAME: "Balance",
        ATTR_ICON: "mdi:cash",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_ATTRIBUTE: "balance",
        ATTR_STATE_SENSITIVE: False,
        ATTR_DEFAULT: True,
    },
    "speed": {
        ATTR_NAME: "Speed",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_ATTRIBUTE: "speed",
        ATTR_STATE_SENSITIVE: True,
    },
    "tachometer": {
        ATTR_NAME: "Tachometer",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: "rpm",
        ATTR_ATTRIBUTE: "engine_rpm",
        ATTR_STATE_SENSITIVE: True,
    },
    "gsm_level": {
        ATTR_NAME: "GSM Level",
        ATTR_ICON: {
            ATTR_DEFAULT: "mdi:network-strength-off",
            0: "mdi:network-strength-1",
            1: "mdi:network-strength-2",
            2: "mdi:network-strength-3",
            3: "mdi:network-strength-4",
        },
        ATTR_ATTRIBUTE: "gsm_level",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
    "battery_voltage": {
        ATTR_NAME: "Battery voltage",
        ATTR_ICON: "mdi:car-battery",
        ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
        ATTR_ATTRIBUTE: "voltage",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DEFAULT: True,
    },
}


class PandoraCASSensor(PandoraCASEntity):
    """Representation of a Pandora Car Alarm System sensor."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    @property
    def state(self) -> Union[None, str, int, float]:
        if self._entity_type == "balance":
            state = self._state
            if state is None:
                return None
            return state.value
        return self._state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        if self._entity_type == "balance":
            state = self._state
            if state is None:
                return None
            return state.currency
        return super().unit_of_measurement


async_setup_entry = partial(
    async_platform_setup_entry, PLATFORM_DOMAIN, PandoraCASSensor, logger=_LOGGER
)
