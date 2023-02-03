"""Sensor platform for Pandora Car Alarm System."""
__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from functools import partial
from typing import Any, Callable, Dict, Optional, Union

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
)
from homeassistant.components.sensor.const import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    SensorDeviceClass.MONETARY,
    SensorDeviceClass.PRESSURE,
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.VOLTAGE,
    LENGTH_KILOMETERS,
    SPEED_KILOMETERS_PER_HOUR,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfLength,
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.core import Event, callback

from . import PandoraCASEntity, async_platform_setup_entry
from .const import *

_LOGGER = logging.getLogger(__name__)

ENTITY_TYPES = {
    "mileage": {
        ATTR_NAME: "Mileage",
        ATTR_ICON: "mdi:map-marker-distance",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
        ATTR_ATTRIBUTE: "mileage",
        ATTR_STATE_SENSITIVE: True,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        ATTR_FORMATTER: lambda v: round(float(v), 2),
    },
    "can_mileage": {
        ATTR_NAME: "CAN Mileage",
        ATTR_ICON: "mdi:map-marker-distance",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
        ATTR_ATTRIBUTE: "can_mileage",
        ATTR_STATE_SENSITIVE: True,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
        ATTR_FORMATTER: lambda v: round(float(v), 2),
    },
    "fuel": {
        ATTR_NAME: "Fuel Level",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_ATTRIBUTE: "fuel",
        ATTR_STATE_SENSITIVE: False,
    },
    "interior_temperature": {
        ATTR_NAME: "Interior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELCIUS,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "interior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "engine_temperature": {
        ATTR_NAME: "Engine Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELCIUS,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "engine_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "exterior_temperature": {
        ATTR_NAME: "Exterior Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELCIUS,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "exterior_temperature",
        ATTR_STATE_SENSITIVE: True,
    },
    "battery_temperature": {
        ATTR_NAME: "Battery Temperature",
        ATTR_ICON: "mdi:thermometer",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELCIUS,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "battery_temperature",
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "balance": {
        ATTR_NAME: "Balance",
        ATTR_ICON: "mdi:cash",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: SensorDeviceClass.MONETARY,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "balance",
        ATTR_STATE_SENSITIVE: False,
    },
    "balance_secondary": {
        ATTR_NAME: "Balance Secondary",
        ATTR_ICON: "mdi:cash",
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: SensorDeviceClass.MONETARY,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "balance_other",
        ATTR_STATE_SENSITIVE: False,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "speed": {
        ATTR_NAME: "Speed",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "speed",
        ATTR_STATE_SENSITIVE: True,
    },
    "tachometer": {
        ATTR_NAME: "Tachometer",
        ATTR_ICON: "mdi:gauge",
        ATTR_UNIT_OF_MEASUREMENT: "rpm",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "engine_rpm",
        ATTR_STATE_SENSITIVE: True,
    },
    "gsm_level": {
        ATTR_NAME: "GSM Level",
        ATTR_ICON: {
            ATTR_DEFAULT: "mdi:sim-off",
            0: "mdi:signal-cellular-outline",
            1: "mdi:signal-cellular-1",
            2: "mdi:signal-cellular-2",
            3: "mdi:signal-cellular-3",
        },
        ATTR_DEVICE_CLASS: "gsm_level",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "gsm_level",
        ATTR_STATE_SENSITIVE: True,
    },
    "battery_voltage": {
        ATTR_NAME: "Battery voltage",
        ATTR_ICON: "mdi:car-battery",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfElectricPotential.VOLT,
        ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_ATTRIBUTE: "voltage",
        ATTR_STATE_SENSITIVE: True,
    },
    "left_front_tire_pressure": {
        ATTR_NAME: "Left Front Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_front_left",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.KPA,
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_front_tire_pressure": {
        ATTR_NAME: "Right Front Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_front_right",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.KPA,
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "left_back_tire_pressure": {
        ATTR_NAME: "Left Back Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_back_left",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.KPA,
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "right_back_tire_pressure": {
        ATTR_NAME: "Right Back Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_back_right",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.KPA,
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "reserve_tire_pressure": {
        ATTR_NAME: "Reserve Tire Pressure",
        ATTR_ICON: "mdi:car-tire-alert",
        ATTR_ATTRIBUTE: "can_tpms_reserve",
        ATTR_UNIT_OF_MEASUREMENT: "kPa",
        ATTR_DEVICE_CLASS: SensorDeviceClass.PRESSURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_STATE_SENSITIVE: True,
        ATTR_DISABLED_BY_DEFAULT: True,
    },
    "track_distance": {
        ATTR_NAME: "Track Distance",
        ATTR_ICON: "mdi:road-variant",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
        ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        ATTR_STATE_SENSITIVE: True,
        ATTR_ATTRIBUTE_SOURCE: lambda d: d.last_point,
        ATTR_ATTRIBUTE: "length",
        ATTR_DISABLED_BY_DEFAULT: False,
    },
}


class PandoraCASSensor(PandoraCASEntity):
    """Representation of a Pandora Car Alarm System sensor."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._points_listener: Optional[Callable] = None

    @property
    def state(self) -> Union[None, str, int, float]:
        entity_type = self._entity_type
        state = self._state

        if entity_type in ("balance", "balance_secondary"):
            if state is None:
                return STATE_UNAVAILABLE
            return state.value

        elif entity_type == "tachometer":
            if state is None:
                return STATE_UNAVAILABLE

            if state < 5:
                return 0

            device_idx = str(self._device.device_id)

            coefficient = None
            coefficient_dict = self._account_cfg.get(CONF_RPM_COEFFICIENT)
            if coefficient_dict:
                coefficient = coefficient_dict.get(device_idx)
                if coefficient is None:
                    coefficient = coefficient_dict.get(ATTR_DEFAULT)

            if coefficient is None:
                coefficient = DEFAULT_RPM_COEFFICIENT

            offset = None
            offset_dict = self._account_cfg.get(CONF_RPM_OFFSET)
            if offset_dict:
                offset = offset_dict.get(device_idx)
                if offset is None:
                    offset = offset_dict.get(ATTR_DEFAULT)

            if offset is None:
                offset = DEFAULT_RPM_OFFSET

            return int(state * coefficient + offset)

        return state

    @property
    def unit_of_measurement(self) -> Optional[str]:
        if self._entity_type in ("balance", "balance_secondary"):
            state = self._state
            if state is None:
                return None
            return state.currency
        return super().unit_of_measurement

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if self._entity_type == "track_distance":

            @callback
            def _event_filter(event: Event):
                return event.data.get("device_id") == self._device.device_id

            async def _schedule_update(*_):
                self.async_schedule_update_ha_state()

            self._points_listener = self.hass.bus.async_listen(
                f"{DOMAIN}_point",
                _schedule_update,
                _event_filter,
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._entity_type == "track_distance":
            points_listener = self._points_listener
            if points_listener is not None:
                self._points_listener = None
                points_listener()

        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        existing_attributes = super().extra_state_attributes
        entity_type = self._entity_type

        if entity_type == "fuel":
            state = self._device.state
            if state is None or not state.fuel_tanks:
                return existing_attributes

            for i, fuel_tank in enumerate(
                sorted(state.fuel_tanks, key=lambda x: x.id), start=1
            ):
                existing_attributes[f"fuel_tank_{i}_id"] = fuel_tank.id
                existing_attributes[
                    f"fuel_tank_{i}_capacity"
                ] = fuel_tank.value

        elif entity_type == "track_distance":
            last_point = self._device.last_point
            if last_point is None:
                existing_attributes.update(
                    dict.fromkeys(
                        (
                            "timestamp",
                            "track_id",
                            "max_speed",
                            "fuel",
                            "latitude",
                            "longitude",
                        )
                    )
                )
            else:
                existing_attributes["timestamp"] = last_point.timestamp
                existing_attributes["track_id"] = last_point.track_id
                existing_attributes["max_speed"] = last_point.max_speed
                existing_attributes["fuel"] = last_point.fuel
                existing_attributes["latitude"] = last_point.latitude
                existing_attributes["longitude"] = last_point.longitude

        return existing_attributes


async_setup_entry = partial(
    async_platform_setup_entry,
    PLATFORM_DOMAIN,
    PandoraCASSensor,
    logger=_LOGGER,
)
