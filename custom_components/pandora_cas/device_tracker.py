"""Device tracker for Pandora Car Alarm System component"""
__all__ = ("async_setup_entry", "PLATFORM_DOMAIN")

import base64
import logging
from typing import Mapping, Any, Dict

from homeassistant.components.device_tracker import (
    DOMAIN as PLATFORM_DOMAIN,
    SOURCE_TYPE_GPS,
    ENTITY_ID_FORMAT,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE
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
    coordinator: PandoraCASUpdateCoordinator
    for coordinator in hass.data[DOMAIN][entry.entry_id].values():
        # Add device tracker
        for entity_type in ENTITY_TYPES:
            new_entities.append(
                PandoraCASTrackerEntity(coordinator, entity_type, None)
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
        online_sensitive=True,
        icon="mdi:car",
    ),
]


class PandoraCASTrackerEntity(PandoraCASEntity, TrackerEntity):
    """Pandora Car Alarm System location tracker."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    _attr_has_entity_name = False

    # def __init__(self, *args, **kwargs) -> None:
    #     super().__init__(*args, **kwargs)
    #
    #     self._latitude_updated = False
    #     self._longitude_updated = False

    @property
    def name(self) -> str | None:
        return self.coordinator.device.name

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attr: Dict[str, StateType] = dict()
        if super_attr := super().extra_state_attributes:
            attr.update(super_attr)

        if not self.available or (value := self._attr_native_value) is None:
            attr.update(
                dict.fromkeys(
                    (
                        ATTR_GSM_LEVEL,
                        ATTR_DIRECTION,
                        ATTR_CARDINAL,
                        ATTR_KEY_NUMBER,
                        ATTR_TAG_NUMBER,
                    )
                )
            )
        else:
            attr[ATTR_GSM_LEVEL] = value.gsm_level
            attr[ATTR_DIRECTION] = value.rotation
            attr[ATTR_CARDINAL] = value.direction
            attr[ATTR_KEY_NUMBER] = value.key_number
            attr[ATTR_TAG_NUMBER] = value.tag_number

        return attr

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        if (device_state := self.coordinator.device.state) is None:
            return 0.0
        return device_state.latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        if (device_state := self.coordinator.device.state) is None:
            return 0.0
        return device_state.longitude

    @property
    def entity_picture(self) -> str:
        device = self.coordinator.device

        return (
            "data:image/svg+xml;base64,"
            + base64.b64encode(
                IMAGE_REGISTRY.get_image(
                    device.car_type,
                    device.color,
                    (device.state.rotation if device.state else None) or 0,
                ).encode()
            ).decode()
        )

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SOURCE_TYPE_GPS
