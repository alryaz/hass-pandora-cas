"""Device tracker for Pandora Car Alarm System component"""

__all__ = ("ENTITY_TYPES", "async_setup_entry")

import asyncio
import base64
import logging
from typing import Mapping, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from haversine import haversine, Unit
from homeassistant.components.device_tracker import ENTITY_ID_FORMAT, SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED, ATTR_DEVICE_ID, ATTR_ID
from homeassistant.core import HomeAssistant, State, Context, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import utcnow
from homeassistant.util.dt import utc_from_timestamp
from ulid_transform import ulid_at_time

from custom_components.pandora_cas.const import *
from custom_components.pandora_cas.entity import (
    PandoraCASEntityDescription,
    PandoraCASEntity,
)
from custom_components.pandora_cas.services import async_get_pandora_id_by_device_id
from custom_components.pandora_cas.tracker_images import IMAGE_REGISTRY
from pandora_cas.data import WsTrack

_LOGGER: Final = logging.getLogger(__name__)

DATA_TRACK_ENTITIES: Final = DOMAIN + "_track_entities"


async def async_load_track(hass: HomeAssistant, call: ServiceCall) -> None:
    # determine device identifier
    param_device_id = call.data[ATTR_DEVICE_ID]
    device_id = async_get_pandora_id_by_device_id(hass, param_device_id)
    if device_id is None:
        raise HomeAssistantError(f"Invalid device ID '{param_device_id}' provided")

    # find device matching identifier
    for entry, coordinator in hass.data[DOMAIN].items():
        if device_id in coordinator.account.devices:
            device = coordinator.account.devices[device_id]
            break
    else:
        raise HomeAssistantError(f"Device with ID '{device_id}' not found.")

    track_id = call.data.get(ATTR_TRACK_ID)
    if track_id is None:
        if not (track := device.state.track):
            raise HomeAssistantError(f"Device has no track associated with")
        track_id = track.track_id
    else:
        # @TODO: add numeric track retrieval
        raise HomeAssistantError(f"Unknown track ID '{track_id}'")

    ent_desc_key = f"track_{track_id}"
    unique_id = f"{DOMAIN}_{device_id}_{ent_desc_key}"

    existing_entities = hass.data.setdefault(DATA_TRACK_ENTITIES, {})
    try:
        track_entity: PandoraCASTrackDisplayEntity = existing_entities[unique_id]
    except KeyError:
        # noinspection PyArgumentList
        coordinator.async_add_entities_per_platform["device_tracker"](
            [
                PandoraCASTrackDisplayEntity(
                    track,
                    coordinator,
                    device,
                    PandoraCASEntityDescription(
                        key=f"track_{track_id}",
                        online_sensitive=False,
                        name=f"Track {track_id}",
                    ),
                )
            ]
        )
    else:
        track_entity.current_track = track
        await track_entity.async_added_to_hass()


ATTR_TRACK_ID = "track_id"

SERVICE_LOAD_TRACK = "load_track"
SERVICE_LOAD_TRACK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Exclusive(ATTR_DEVICE_ID, ATTR_DEVICE_ID): cv.string,
            vol.Exclusive(ATTR_ID, ATTR_DEVICE_ID): cv.string,
            vol.Optional(ATTR_TRACK_ID): cv.positive_int,
        },
        extra=vol.ALLOW_EXTRA,
    ),
    cv.deprecated(ATTR_ID, ATTR_DEVICE_ID),
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    from custom_components.pandora_cas import PandoraCASUpdateCoordinator

    new_entities = []
    coordinator: PandoraCASUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_add_entities_per_platform["device_tracker"] = async_add_entities
    for device in coordinator.account.devices.values():
        # Add device tracker
        for entity_type in ENTITY_TYPES:
            new_entities.append(
                PandoraCASTrackerEntity(coordinator, device, entity_type, None)
            )

    if new_entities:
        async_add_entities(new_entities)

    # # @TODO: disabled temporarily
    # if not hass.services.has_service(DOMAIN, SERVICE_LOAD_TRACK):
    #     hass.services.async_register(
    #         DOMAIN,
    #         SERVICE_LOAD_TRACK,
    #         partial(async_load_track, hass),
    #         schema=SERVICE_LOAD_TRACK_SCHEMA,
    #     )

    return True


# noinspection PyArgumentList
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


class BasePandoraCASTrackerEntity(PandoraCASEntity, TrackerEntity):
    _attr_latitude = None
    _attr_longitude = None

    @property
    def location_accuracy(self) -> int:
        # This value is always present due to init
        return int(self._device_config[CONF_COORDINATES_DEBOUNCE])

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._attr_latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._attr_longitude


class PandoraCASTrackerEntity(BasePandoraCASTrackerEntity):
    """Pandora Car Alarm System location tracker."""

    ENTITY_TYPES = ENTITY_TYPES
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    _attr_has_entity_name = False

    @property
    def name(self) -> str | None:
        return self.pandora_device.name

    def update_native_value(self) -> None:
        super().update_native_value()

        if not self.available:
            return

        # Ignore WS coordinates if required
        if (
            self.coordinator.is_last_update_ws
            and self._device_config[CONF_IGNORE_WS_COORDINATES]
        ):
            self.logger.debug("Ignored WS coordinates update per setting")
            return

        # Ignore updates without data
        if not (device_data := self.coordinator_device_data):
            return

        # Ignore updates with a single non-zero coordinate
        new_ll = (
            device_data.get("latitude") or None,
            device_data.get("longitude") or None,
        )
        if new_ll == (None, None):
            return
        if None in new_ll:
            self.logger.debug("Ignored WS single coordinate update")
            return

        # Update if no coordinates yet exist, or difference is above threshold
        if not all(old_ll := (self._attr_latitude, self._attr_longitude)) or (
            haversine(old_ll, new_ll, unit=Unit.METERS)
            >= self._device_config[CONF_COORDINATES_DEBOUNCE]
        ):
            self._attr_latitude, self._attr_longitude = new_ll

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attr: dict[str, StateType] = dict()
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
    def final_car_type(self) -> str | None:
        if (
            cursor_type := self._device_config[CONF_CUSTOM_CURSOR_TYPE]
        ) == DEFAULT_CURSOR_TYPE:
            return self.pandora_device.car_type
        if cursor_type != DISABLED_CURSOR_TYPE:
            return cursor_type
        return None

    @property
    def entity_picture(self) -> str | None:
        if (
            cursor := self._device_config[CONF_CUSTOM_CURSOR_TYPE]
        ) == DISABLED_CURSOR_TYPE:
            return None
        device = self.pandora_device
        if cursor == DEFAULT_CURSOR_TYPE:
            cursor = device.car_type

        return (
            "data:image/svg+xml;base64,"
            + base64.b64encode(
                IMAGE_REGISTRY.get_image(
                    cursor,
                    device.color,
                    (
                        device.state.rotation
                        if device.state
                        and not self._device_config[CONF_DISABLE_CURSOR_ROTATION]
                        else None
                    )
                    or 0,
                ).encode()
            ).decode()
        )

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SourceType.GPS


class PandoraCASTrackDisplayEntity(BasePandoraCASTrackerEntity):
    ENTITY_ID_FORMAT = ENTITY_ID_FORMAT

    _attr_should_poll = False

    def __init__(self, track: WsTrack, *args, **kwargs) -> None:
        self.current_track = track
        super().__init__(*args, **kwargs)

    @property
    def latitude(self) -> float | None:
        return self._attr_latitude

    @property
    def longitude(self) -> float | None:
        return self._attr_longitude

    async def async_added_to_hass(self) -> None:
        from homeassistant.components.recorder import get_instance

        self.hass.data[DATA_TRACK_ENTITIES][self.unique_id] = self
        await super().async_added_to_hass()
        if not self.current_track.points:
            _LOGGER.error(f"Current track has no points")
            self._attr_available = False
            return

        try:
            recorder_instance = get_instance(self.hass)
        except LookupError:
            _LOGGER.error(f"Recorder unavailable")
            self._attr_available = False
            return

        from homeassistant.components.recorder.purge import purge_entity_data

        # Remove all records
        while not await recorder_instance.async_add_executor_job(
            purge_entity_data,
            recorder_instance,
            lambda x: x == self.entity_id,
            last_time := utcnow(),
        ):
            _LOGGER.debug(f"Performed failed purge of {self.entity_id} at {last_time}")
            await asyncio.sleep(1.0)
        _LOGGER.debug(f"Performed successful purge of {self.entity_id} at {last_time}")

        # Remove existing entity state
        states = self.hass.states
        async_fire = self.hass.bus.async_fire
        states.async_remove(self.entity_id)

        entity_id = self.entity_id
        old_state = None
        for i, point in enumerate(self.current_track.points):
            self._attr_latitude = point.latitude
            self._attr_longitude = point.longitude
            self._attr_extra_state_attributes = {
                "fuel": point.fuel,
                "speed": point.speed,
                "flags": point.flags,
            }
            timestamp = utc_from_timestamp(point.timestamp)
            context = Context(id=ulid_at_time(point.timestamp))
            calculated_state = self._async_calculate_state()

            new_state = State(
                entity_id,
                calculated_state.state,
                calculated_state.attributes,
                timestamp,
                timestamp,
                timestamp,
                context,
                not i,
                None,
            )

            _LOGGER.debug(f"Writing obsolete state: {new_state}")

            # @TODO: find a better solution than copying everything from core
            # noinspection PyProtectedMember
            states._states[entity_id] = new_state
            async_fire(
                EVENT_STATE_CHANGED,
                {
                    "entity_id": entity_id,
                    "old_state": old_state,
                    "new_state": new_state,
                },
                context=context,
                time_fired=timestamp,
            )

            old_state = new_state

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self.hass.data[DATA_TRACK_ENTITIES].pop(self.unique_id, None)
        await self.async_will_remove_from_hass()

    @property
    def name(self) -> str:
        return f"Track #{self.current_track.track_id}"

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SourceType.GPS
