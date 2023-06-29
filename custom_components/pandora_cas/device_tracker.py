"""Device tracker for Pandora Car Alarm System component"""
__all__ = ("ENTITY_TYPES", "async_setup_entry")

import base64
import logging
from typing import Mapping, Any, Dict, Optional

from haversine import haversine, Unit
from homeassistant.components.device_tracker import (
    ENTITY_ID_FORMAT,
    SourceType,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from custom_components.pandora_cas.const import *
from custom_components.pandora_cas.entity import (
    PandoraCASEntity,
)
from custom_components.pandora_cas.entity import (
    PandoraCASUpdateCoordinator,
    PandoraCASEntityDescription,
)
from custom_components.pandora_cas.tracker_images import IMAGE_REGISTRY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    new_entities = []
    coordinator: PandoraCASUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    for device in coordinator.account.devices.values():
        # Add device tracker
        for entity_type in ENTITY_TYPES:
            new_entities.append(
                PandoraCASTrackerEntity(coordinator, device, entity_type, None)
            )

    if new_entities:
        async_add_entities(new_entities)

    return True


ENTITY_TYPES = [
    PandoraCASEntityDescription(
        key="pandora",
        name="Pandora",
        attribute="state",
        attribute_source=None,
        icon="mdi:car",
        online_sensitive=False,
    ),
]


class PandoraCASTrackerEntity(PandoraCASEntity, TrackerEntity):
    """Pandora Car Alarm System location tracker."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    _attr_has_entity_name = False

    def __init__(self, *args, **kwargs) -> None:
        self._last_latitude = None
        self._last_longitude = None

        super().__init__(*args, **kwargs)

    @property
    def name(self) -> str | None:
        return self.pandora_device.name

    def update_native_value(self) -> bool:
        super().update_native_value()

        if not self.available:
            return True

        state = self.pandora_device.state
        old_ll = (self._last_latitude, self._last_longitude)
        if not all(old_ll):
            self._last_latitude = state.latitude
            self._last_longitude = state.longitude
            return True

        new_ll = (state.latitude, state.longitude)
        if haversine(old_ll, new_ll, unit=Unit.METERS) >= 10.0:
            self._last_latitude, self._last_longitude = new_ll
            return True
        return False

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attr: Dict[str, StateType] = dict()
        if super_attr := super().extra_state_attributes:
            attr.update(super_attr)

        if not self.available or (value := self._attr_native_value) is None:
            attr.update(
                dict.fromkeys(
                    (
                        ATTR_ROTATION,
                        ATTR_CARDINAL,
                    )
                )
            )
        else:
            attr[ATTR_ROTATION] = value.rotation
            attr[ATTR_CARDINAL] = value.direction

        return attr

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._last_latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._last_longitude

    @property
    def final_car_type(self) -> Optional[str]:
        if (
            cursor_type := self._device_config[CONF_CUSTOM_CURSOR_TYPE]
        ) == DEFAULT_CURSOR_TYPE:
            return self.pandora_device.car_type
        if cursor_type != DISABLED_CURSOR_TYPE:
            return cursor_type
        return None

    @property
    def entity_picture(self) -> Optional[str]:
        if (
            cursor := self._device_config[CONF_CUSTOM_CURSOR_TYPE]
        ) == DISABLED_CURSOR_TYPE:
            return
        device = self.pandora_device
        if cursor == DEFAULT_CURSOR_TYPE:
            cursor = device.car_type

        return (
            "data:image/svg+xml;base64,"
            + base64.b64encode(
                IMAGE_REGISTRY.get_image(
                    cursor,
                    device.color,
                    (device.state.rotation if device.state else None) or 0,
                ).encode()
            ).decode()
        )

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SourceType.GPS
