"""Sensor platform for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Mapping, Hashable

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntityDescription,
    SensorEntity,
)
from homeassistant.components.sensor.const import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfLength,
    UnitOfTemperature,
    PERCENTAGE,
    ATTR_ID,
    ATTR_LONGITUDE,
    ATTR_LATITUDE,
    EntityCategory,
    UnitOfSpeed,
    REVOLUTIONS_PER_MINUTE,
    UnitOfVolume,
)
from homeassistant.core import Event, callback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utc_from_timestamp

from pandora_cas.data import Balance, CurrentState, TrackingPoint
from custom_components.pandora_cas.const import *
from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASEntityDescription,
    PandoraCASEntity,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class PandoraCASSensorEntityDescription(
    PandoraCASEntityDescription, SensorEntityDescription
):
    icon_states: Mapping[Hashable, str] | None = None


# noinspection PyArgumentList
ENTITY_TYPES = [
    PandoraCASSensorEntityDescription(
        key="mileage",
        name="Mileage",
        icon="mdi:map-marker-distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        attribute=CurrentState.mileage,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
    ),
    PandoraCASSensorEntityDescription(
        key="can_mileage",
        name="CAN Mileage",
        attribute=CurrentState.can_mileage,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
    ),
    PandoraCASSensorEntityDescription(
        key="can_mileage_to_empty",
        name="CAN Mileage to empty",
        attribute=CurrentState.can_mileage_to_empty,
        native_unit_of_measurement=UnitOfLength.MILES,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSensorEntityDescription(
        key="can_mileage_by_battery",
        name="CAN Mileage batt",
        attribute=CurrentState.can_mileage_by_battery,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
    ),
    PandoraCASSensorEntityDescription(
        key="fuel",
        name="Fuel Level",
        icon="mdi:fuel",
        native_unit_of_measurement=PERCENTAGE,
        attribute=CurrentState.fuel,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PandoraCASSensorEntityDescription(
        key="fuel_consumption",
        name="Fuel Consumption",
        icon="mdi:fuel",
        attribute=CurrentState.can_consumption,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    # PandoraCASSensorEntityDescription(
    #     key="fuel_consumption",
    #     name="Fuel Consumption After",
    #     icon="mdi:fuel",
    #     attribute=CurrentState.can_consumption_after,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     suggested_display_precision=2,
    #     entity_registry_enabled_default=False,
    # ),
    PandoraCASSensorEntityDescription(
        key="soc",
        name="State Of Charge",
        icon="mdi:battery",
        native_unit_of_measurement=PERCENTAGE,
        attribute=CurrentState.ev_state_of_charge,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PandoraCASSensorEntityDescription(
        key="interior_temperature",
        name="Interior Temperature",
        icon="mdi:thermometer",
        attribute=CurrentState.interior_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="engine_temperature",
        name="Engine Temperature",
        attribute=CurrentState.engine_temperature,
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="exterior_temperature",
        name="Exterior Temperature",
        attribute=CurrentState.exterior_temperature,
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="battery_temperature",
        name="Battery Temperature",
        attribute=CurrentState.battery_temperature,
        entity_registry_enabled_default=False,
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="balance",
        name="Balance",
        icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        attribute=CurrentState.balance,
    ),
    PandoraCASSensorEntityDescription(
        key="balance_secondary",
        name="Balance Secondary",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        attribute=CurrentState.balance_other,
    ),
    PandoraCASSensorEntityDescription(
        key="speed",
        name="Speed",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        attribute=CurrentState.speed,
    ),
    PandoraCASSensorEntityDescription(
        key="tachometer",
        name="Tachometer",
        icon="mdi:gauge",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attribute=CurrentState.engine_rpm,
    ),
    PandoraCASSensorEntityDescription(
        key="gsm_level",
        name="GSM Level",
        icon="mdi:sim-off",
        icon_states={
            0: "mdi:signal-cellular-outline",
            1: "mdi:signal-cellular-1",
            2: "mdi:signal-cellular-2",
            3: "mdi:signal-cellular-3",
        },
        # device_class="gsm_level",
        state_class=SensorStateClass.MEASUREMENT,
        attribute=CurrentState.gsm_level,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PandoraCASSensorEntityDescription(
        key="battery_voltage",
        name="Battery voltage",
        icon="mdi:car-battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        attribute=CurrentState.voltage,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="left_front_tire_pressure",
        name="Left Front Tire Pressure",
        icon="mdi:car-tire-alert",
        attribute=CurrentState.can_tpms_front_left,
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="right_front_tire_pressure",
        name="Right Front Tire Pressure",
        attribute=CurrentState.can_tpms_front_right,
        icon="mdi:car-tire-alert",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="left_back_tire_pressure",
        name="Left Back Tire Pressure",
        attribute=CurrentState.can_tpms_back_left,
        icon="mdi:car-tire-alert",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="right_back_tire_pressure",
        name="Right Back Tire Pressure",
        attribute=CurrentState.can_tpms_back_right,
        icon="mdi:car-tire-alert",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="reserve_tire_pressure",
        name="Reserve Tire Pressure",
        attribute=CurrentState.can_tpms_reserve,
        icon="mdi:car-tire-alert",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    PandoraCASSensorEntityDescription(
        key="track_distance",
        name="Track Distance",
        icon="mdi:road-variant",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        attribute_source="last_point",
        attribute=TrackingPoint.length,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSensorEntityDescription(
        key="key_number",
        name="Key Number",
        icon="mdi:key",
        state_class=SensorStateClass.MEASUREMENT,
        attribute=CurrentState.key_number,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSensorEntityDescription(
        key="tag_number",
        name="Tag Number",
        icon="mdi:tag",
        state_class=SensorStateClass.MEASUREMENT,
        attribute=CurrentState.tag_number,
        entity_registry_enabled_default=False,
    ),
    PandoraCASSensorEntityDescription(
        key="last_online",
        name="Last Online",
        attribute=CurrentState.online_timestamp_utc,
        icon="mdi:cloud-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        online_sensitive=False,
    ),
    PandoraCASSensorEntityDescription(
        key="last_state_update",
        name="Last State Update",
        icon="mdi:message-text-clock",
        attribute=CurrentState.state_timestamp_utc,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        online_sensitive=False,
    ),
    PandoraCASSensorEntityDescription(
        key="last_settings_change",
        name="Last Settings Change",
        icon="mdi:wrench-clock",
        attribute=CurrentState.settings_timestamp_utc,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        online_sensitive=False,
    ),
    PandoraCASSensorEntityDescription(
        key="last_command_execution",
        name="Last Command Execution",
        icon="mdi:send-variant-clock",
        attribute=CurrentState.command_timestamp_utc,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        online_sensitive=False,
    ),
    # PandoraCASSensorEntityDescription(
    #     key="last_event",
    #     name="Last Event",
    #     icon="mdi:timeline-alert",
    #     attribute="last_event",
    #     attribute_source=None,
    #     online_sensitive=False,
    # ),
]


class PandoraCASSensor(PandoraCASEntity, SensorEntity):
    """Representation of a Pandora Car Alarm System sensor."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    entity_description: PandoraCASSensorEntityDescription

    def __init__(self, *args, extra_identifier: Any = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._points_listener: Callable[[], None] | None = None
        self._extra_identifier = extra_identifier
        self._last_timestamp = None

        key = self.entity_description.key
        if (key.startswith("mileage") and self._device_config[CONF_MILEAGE_MILES]) or (
            key.startswith("can_mileage")
            and self._device_config[CONF_MILEAGE_CAN_MILES]
        ):
            self._attr_native_unit_of_measurement = UnitOfLength.MILES

    @property
    def icon(self) -> str | None:
        if (icons := self.entity_description.icon_states) and (
            state_icon := icons.get(self._attr_native_value)
        ):
            return state_icon
        return super().icon

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attributes: dict[str, StateType] = dict()
        if super_attr := super().extra_state_attributes:
            attributes.update(super_attr)

        key = self.entity_description.key
        if key == "fuel":
            # target_fuel_tank = None
            # if state := self.pandora_device.state:
            #     for fuel_tank in state.fuel_tanks:
            #         if fuel_tank.id == self._extra_identifier:
            #             target_fuel_tank = fuel_tank
            #             break
            #
            #         break
            #
            # if target_fuel_tank:
            #     attributes[ATTR_ID] = target_fuel_tank.id
            #     attributes["capacity"] = target_fuel_tank.value
            # else:
            #     attributes.update(dict.fromkeys((ATTR_ID, "capacity")))

            if self._device_config[CONF_FUEL_IS_LITERS]:
                # @TODO: this is presentation-only, check registry
                self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
                self._attr_device_class = SensorDeviceClass.VOLUME_STORAGE

        elif key == "track_distance":
            if last_point := self.pandora_device.last_point:
                attributes[ATTR_ID] = last_point.device_id
                attributes["timestamp"] = last_point.timestamp
                attributes["track_id"] = last_point.track_id
                attributes["max_speed"] = last_point.max_speed
                attributes["fuel"] = last_point.fuel
                attributes[ATTR_LATITUDE] = last_point.latitude
                attributes[ATTR_LONGITUDE] = last_point.longitude
            else:
                attributes.update(
                    dict.fromkeys(
                        (
                            ATTR_ID,
                            "timestamp",
                            "track_id",
                            "max_speed",
                            "fuel",
                            ATTR_LATITUDE,
                            ATTR_LONGITUDE,
                        )
                    )
                )

        elif key.startswith("balance"):
            attributes[ATTR_PHONE_NUMBER] = getattr(
                self.pandora_device, "phone" + key[7:], None
            )

        return attributes

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if self.entity_description.key == "track_distance":

            @callback
            def _event_filter(event: Event):
                return event.data.get("device_id") == self.pandora_device.device_id

            async def _schedule_update(*_):
                self.async_schedule_update_ha_state()

            self._points_listener = self.hass.bus.async_listen(
                f"{DOMAIN}_point",
                _schedule_update,
                _event_filter,
            )

    async def async_will_remove_from_hass(self) -> None:
        if (points_listener := self._points_listener) is not None:
            self._points_listener = None
            points_listener()

        await super().async_will_remove_from_hass()

    def get_native_value(self) -> Any | None:
        native_value = super().get_native_value()
        if self.entity_description.key == "tachometer":
            if native_value:
                return int(
                    native_value * self._device_config[CONF_RPM_COEFFICIENT]
                    + self._device_config[CONF_RPM_OFFSET]
                )
            return 0
        return native_value

    def update_native_value(self) -> None:
        last_value = self._attr_native_value
        super().update_native_value()

        native_value = self._attr_native_value
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            if native_value is None:
                native_value = last_value
            if isinstance(native_value, (int, float)):
                self._attr_available = True
                self._attr_native_value = utc_from_timestamp(native_value)
            else:
                self._attr_available = False
        elif isinstance(native_value, Balance):
            self._attr_native_value = native_value.value
            self._attr_native_unit_of_measurement = native_value.currency
        elif self.entity_description.key == "fuel":
            if self._attr_native_value == 0:
                fuel_drop_threshold = self._device_config[CONF_FILTER_FUEL_DROPS]
                if fuel_drop_threshold > 0 and last_value >= fuel_drop_threshold:
                    self._attr_native_value = last_value
                    self.logger.debug(f"Filtered fuel drop to zero from {last_value}")


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASSensor,
    logger=_LOGGER,
)
