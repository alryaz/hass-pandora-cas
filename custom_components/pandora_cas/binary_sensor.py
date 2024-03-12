"""Binary sensor platform for Pandora Car Alarm System."""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import logging
from functools import partial
from typing import Mapping, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.typing import StateType

from custom_components.pandora_cas.entity import (
    async_platform_setup_entry,
    PandoraCASBooleanEntity,
    PandoraCASBooleanEntityDescription,
)
from pandora_cas.enums import BitStatus

_LOGGER = logging.getLogger(__name__)

_ICON_CAR_DOOR_ON = "mdi:car-door"
_ICON_CAR_DOOR_OFF = "mdi:car-door-lock"
_ICON_CAR_GLASS_ON = "mdi:car-windshield-outline"
_ICON_CAR_GLASS_OFF = "mdi:car-windshield"
_ICON_SAFETY_BELT_ON = "mdi:seatbelt"
_ICON_SAFETY_BELT_OFF = "mdi:car-seat"

# noinspection PyArgumentList
ENTITY_TYPES = [
    PandoraCASBooleanEntityDescription(
        key="connection_state",
        name="Connection state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        attribute="is_online",
        attribute_source=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        online_sensitive=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="moving",
        name="Moving",
        device_class=BinarySensorDeviceClass.MOTION,
        attribute="is_moving",
    ),
    # Status-related sensors
    PandoraCASBooleanEntityDescription(
        key="driver_door",
        name="Driver Door",
        icon=_ICON_CAR_DOOR_ON,
        icon_off=_ICON_CAR_DOOR_OFF,
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.DOOR_DRIVER_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="passenger_door",
        name="Passenger Door",
        icon=_ICON_CAR_DOOR_ON,
        icon_off=_ICON_CAR_DOOR_OFF,
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.DOOR_PASSENGER_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="left_back_door",
        name="Left Back Door",
        icon=_ICON_CAR_DOOR_ON,
        icon_off=_ICON_CAR_DOOR_OFF,
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.DOOR_BACK_LEFT_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="right_back_door",
        name="Right Back Door",
        icon=_ICON_CAR_DOOR_ON,
        icon_off=_ICON_CAR_DOOR_OFF,
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.DOOR_BACK_RIGHT_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="driver_glass",
        name="Driver Glass",
        icon=_ICON_CAR_GLASS_ON,
        icon_off=_ICON_CAR_GLASS_OFF,
        device_class=BinarySensorDeviceClass.WINDOW,
        attribute="can_glass_driver",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="passenger_glass",
        name="Passenger Glass",
        icon=_ICON_CAR_GLASS_ON,
        icon_off=_ICON_CAR_GLASS_OFF,
        device_class=BinarySensorDeviceClass.WINDOW,
        attribute="can_glass_passenger",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="left_back_glass",
        name="Left Back Glass",
        icon=_ICON_CAR_GLASS_ON,
        icon_off=_ICON_CAR_GLASS_OFF,
        device_class=BinarySensorDeviceClass.WINDOW,
        attribute="can_glass_back_left",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="right_back_glass",
        name="Right Back Glass",
        icon=_ICON_CAR_GLASS_ON,
        icon_off=_ICON_CAR_GLASS_OFF,
        device_class=BinarySensorDeviceClass.WINDOW,
        attribute="can_glass_back_right",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="driver_safety_belt",
        name="Driver Safety Belt",
        icon=_ICON_SAFETY_BELT_ON,
        icon_off=_ICON_SAFETY_BELT_OFF,
        device_class=BinarySensorDeviceClass.SAFETY,
        attribute="can_belt_driver",
        entity_registry_enabled_default=False,
        inverse=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="passenger_safety_belt",
        name="Passenger Safety Belt",
        icon=_ICON_SAFETY_BELT_ON,
        icon_off=_ICON_SAFETY_BELT_OFF,
        device_class=BinarySensorDeviceClass.SAFETY,
        attribute="can_belt_passenger",
        entity_registry_enabled_default=False,
        inverse=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="left_back_safety_belt",
        name="Left Back Safety Belt",
        icon=_ICON_SAFETY_BELT_ON,
        icon_off=_ICON_SAFETY_BELT_OFF,
        device_class=BinarySensorDeviceClass.SAFETY,
        attribute="can_belt_back_left",
        entity_registry_enabled_default=False,
        inverse=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="right_back_safety_belt",
        name="Right Back Safety Belt",
        icon=_ICON_SAFETY_BELT_ON,
        icon_off=_ICON_SAFETY_BELT_OFF,
        device_class=BinarySensorDeviceClass.SAFETY,
        attribute="can_belt_back_right",
        entity_registry_enabled_default=False,
        inverse=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="center_back_safety_belt",
        name="Center Back Safety Belt",
        icon=_ICON_SAFETY_BELT_ON,
        icon_off=_ICON_SAFETY_BELT_OFF,
        device_class=BinarySensorDeviceClass.SAFETY,
        attribute="can_belt_back_center",
        entity_registry_enabled_default=False,
        inverse=True,
    ),
    PandoraCASBooleanEntityDescription(
        key="seat_taken",
        name="Seat Taken",
        icon="mdi:seat-passenger",
        icon_off="mdi:car-seat",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        attribute="can_seat_taken",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="trunk",
        name="Trunk",
        icon="mdi:car-back",
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.TRUNK_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="hood",
        name="Hood",
        icon="mdi:car",
        device_class=BinarySensorDeviceClass.DOOR,
        attribute="bit_state",
        flag=BitStatus.HOOD_OPEN,
    ),
    PandoraCASBooleanEntityDescription(
        key="parking",
        name="Parking Mode",
        icon="mdi:car-brake-parking",
        attribute="bit_state",
        flag=BitStatus.HANDBRAKE_ENGAGED,
    ),
    PandoraCASBooleanEntityDescription(
        key="brakes",
        name="Brakes",
        icon="mdi:car-brake-hold",
        attribute="bit_state",
        flag=BitStatus.BRAKES_ENGAGED,
    ),
    PandoraCASBooleanEntityDescription(
        key="ignition",
        name="Ignition",
        icon="mdi:key-variant",
        attribute="bit_state",
        flag=BitStatus.IGNITION,
    ),
    PandoraCASBooleanEntityDescription(
        key="exterior_lights",
        name="Exterior Lights",
        icon="mdi:car-light-high",
        device_class=BinarySensorDeviceClass.LIGHT,
        attribute="bit_state",
        flag=BitStatus.EXTERIOR_LIGHTS_ACTIVE,
    ),
    PandoraCASBooleanEntityDescription(
        key="evacuation_mode",
        name="Evacuation Mode",
        icon="mdi:train-car-flatbed-car",
        icon_off="mdi:train-car-flatbed",
        attribute="bit_state",
        flag=BitStatus.EVACUATION_MODE_ACTIVE,
    ),
    PandoraCASBooleanEntityDescription(
        key="ev_charging_connected",
        name="EV Charging Connected",
        icon="mdi:ev-station",
        attribute="ev_charging_connected",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="can_low_liquid",
        name="CAN Low Liquid",
        icon="mdi:wiper",
        icon_on="mdi:wiper-wash-alert",
        icon_off="mdi:wiper-wash",
        device_class=BinarySensorDeviceClass.PROBLEM,
        attribute="can_low_liquid",
        entity_registry_enabled_default=False,
    ),
    PandoraCASBooleanEntityDescription(
        key="engine_locked",
        name="Engine Locked",
        icon_off="mdi:check-circle",
        icon_on="mdi:alert-octagon",
        icon="mdi:cancel",
        attribute="bit_state",
        flag=BitStatus.ENGINE_LOCKED,
    ),
]


class PandoraCASBinarySensor(PandoraCASBooleanEntity, BinarySensorEntity):
    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    @property
    def is_on(self) -> bool | None:
        if self.available:
            return self._attr_native_value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attributes: dict[str, StateType] = dict()
        if super_attr := super().extra_state_attributes:
            attributes.update(super_attr)

        key = self.entity_description.key
        state = self.pandora_device.state

        if key == "ev_charging_connected":
            if self.available and state:
                attributes["slow_charging"] = state.ev_charging_slow
                attributes["fast_charging"] = state.ev_charging_fast
                attributes["ready_status"] = state.ev_status_ready
            else:
                attributes.update(
                    dict.fromkeys(("slow_charging", "fast_charging", "ready_status"))
                )

        # # @TODO: fix for StateType typing
        # elif key == "connection_state":
        #     attributes.update(
        #         attr.asdict(state, True)
        #         if state
        #         else dict.fromkeys(attr.fields_dict(CurrentState))
        #     )

        return attributes


async_setup_entry = partial(
    async_platform_setup_entry,
    PandoraCASBinarySensor,
    logger=_LOGGER,
)
