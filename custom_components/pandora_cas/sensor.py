"""Sensor platform for Pandora Car Alarm System."""
__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from functools import partial
from typing import Any, Dict, Optional, Union

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    LENGTH_KILOMETERS,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
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
        ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
        ATTR_FORMATTER: lambda v: round(float(v), 2),
    },
    "can_mileage": {
        ATTR_NAME: "CAN Mileage",
        ATTR_ICON: "mdi:map-marker-distance",
        ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
        ATTR_ATTRIBUTE: "can_mileage",
        ATTR_STATE_SENSITIVE: True,
        ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
        ATTR_FORMATTER: lambda v: round(float(v), 2),
    },
    "fuel": {
        ATTR_NAME: "Fuel Level",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: "%",
        ATTR_ATTRIBUTE: "fuel",
        ATTR_STATE_SENSITIVE: False,
    },
    "interior_temperature": {
        ATTR_NAME: "Interior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "interior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "engine_temperature": {
        ATTR_NAME: "Engine Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "engine_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "exterior_temperature": {
        ATTR_NAME: "Exterior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "exterior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "battery_temperature": {
        ATTR_NAME: "Battery Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "battery_temperature",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "balance": {
        ATTR_NAME: "Balance",
        ATTR_ICON: "mdi:cash",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_MONETARY,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "balance",
        ATTR_STATE_SENSITIVE: False,
    },
    "speed": {
        ATTR_NAME: "Speed",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "speed",
        ATTR_STATE_SENSITIVE: True,
    },
    "tachometer": {
        ATTR_NAME: "Tachometer",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: "rpm",
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
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
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "gsm_level",
        ATTR_STATE_SENSITIVE: True,
    },
    "battery_voltage": {
        ATTR_NAME: "Battery voltage",
        ATTR_ICON: "mdi:car-battery",
        ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_ATTRIBUTE: "voltage",
        ATTR_STATE_SENSITIVE: True,
    },
    "left_front_tire_pressure": {
        ATTR_NAME: "Left Front Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_front_left",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_front_tire_pressure": {
        ATTR_NAME: "Right Front Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_front_right",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "left_back_tire_pressure": {
        ATTR_NAME: "Left Back Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_back_left",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_back_tire_pressure": {
        ATTR_NAME: "Right Back Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_back_right",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
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

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        existing_attributes = super().device_state_attributes
        if self._entity_type != "fuel":
            return existing_attributes

        state = self._device.state
        if state is None or not state.fuel_tanks:
            return existing_attributes

        for i, fuel_tank in enumerate(
            sorted(state.fuel_tanks, key=lambda x: x.id), start=1
        ):
            existing_attributes[f"fuel_tank_{i}_id"] = fuel_tank.id
            existing_attributes[f"fuel_tank_{i}_capacity"] = fuel_tank.value

        return existing_attributes


async_setup_entry = partial(
    async_platform_setup_entry, PLATFORM_DOMAIN, PandoraCASSensor, logger=_LOGGER
)
