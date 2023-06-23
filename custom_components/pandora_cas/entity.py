import asyncio
import dataclasses
import logging
from dataclasses import dataclass
from enum import Flag
from typing import (
    Type,
    Set,
    Optional,
    Callable,
    ClassVar,
    Collection,
    Any,
    Union,
    Mapping,
    Dict,
    final,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.entity import EntityDescription, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)
from homeassistant.util import slugify

from custom_components.pandora_cas.api import (
    PandoraOnlineDevice,
    Features,
    CommandID,
)
from custom_components.pandora_cas.const import DOMAIN, ATTR_COMMAND_ID

_LOGGER = logging.getLogger(__name__)


async def async_platform_setup_entry(
    entity_class: Type["PandoraCASEntity"],
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    logger: logging.Logger = _LOGGER,
):
    """Generic platform setup function"""
    platform_id = async_get_current_platform()
    logger.debug(
        f'Setting up platform "{platform_id.domain}" with '
        f'entity class "{entity_class.__name__}"'
    )

    new_entities = []
    coordinator: PandoraCASUpdateCoordinator
    for coordinator in hass.data[DOMAIN][entry.entry_id].values():
        device = coordinator.device

        # Apply filters
        for entity_description in entity_class.ENTITY_TYPES:
            if (features := entity_description.features) is not None and (
                device.features is None or not features & device.features
            ):
                entity_description = dataclasses.replace(
                    entity_description,
                    entity_registry_enabled_default=False,
                )

            new_entities.append(entity_class(coordinator, entity_description))

    if new_entities:
        async_add_entities(new_entities)
        logger.debug(
            f'Added {len(new_entities)} new "{platform_id.domain}" entities for account '
            f'"{entry.data[CONF_USERNAME]}": {", ".join(e.entity_id for e in new_entities)}'
        )

    return True


class PandoraCASUpdateCoordinator(DataUpdateCoordinator[Mapping[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        device: PandoraOnlineDevice,
        **kwargs,
    ) -> None:
        self.device = device

        super().__init__(hass, _LOGGER, name=DOMAIN, **kwargs)

    async def _async_update_data(self) -> Set[str]:
        """Fetch data for sub-entities."""
        # @TODO: manual polling updates!
        raise NotImplementedError


@dataclass
class PandoraCASEntityDescription(EntityDescription):
    attribute: Optional[str] = None
    attribute_source: Optional[str] = "state"
    online_sensitive: Optional[bool] = False
    features: Optional[Features] = None
    assumed_state: bool = False


class PandoraCASEntity(CoordinatorEntity[PandoraCASUpdateCoordinator]):
    ENTITY_TYPES: ClassVar[
        Collection[PandoraCASEntityDescription]
    ] = NotImplemented
    ENTITY_ID_FORMAT: ClassVar[str] = NotImplemented

    _attr_native_value: Any
    entity_description: PandoraCASEntityDescription

    _attr_has_entity_name = True
    """Do not poll entities (handled by central account updaters)."""

    def __init__(
        self,
        coordinator: PandoraCASUpdateCoordinator,
        entity_description: "PandoraCASEntityDescription",
        extra_identifier: Any = None,
        context: Any = None,
    ) -> None:
        super().__init__(coordinator, context)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key

        # Set unique ID based on entity type
        device = self.coordinator.device
        unique_id = f"{DOMAIN}_{device.device_id}_{entity_description.key}"
        if extra_identifier is not None:
            unique_id += f"_{extra_identifier}"
        self._attr_unique_id = unique_id
        self._extra_identifier = extra_identifier
        self.entity_id = self.ENTITY_ID_FORMAT.format(
            f"{slugify(str(device.device_id))}_{slugify(entity_description.key)}"
        )

        # First attributes update
        self._attr_native_value = None
        self.update_native_value()

    @property
    def device_info(self) -> DeviceInfo | None:
        d = self.coordinator.device
        return DeviceInfo(
            identifiers={(DOMAIN, str(d.device_id))},
            default_name=d.name,
            manufacturer="Pandora",
            model=d.model,
            sw_version=f"{d.firmware_version} / {d.voice_version}",
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        attr: Dict[str, StateType] = dict()
        if super_attr := super().extra_state_attributes:
            attr.update(super_attr)

        attr[ATTR_DEVICE_ID] = self.coordinator.device.device_id

        return attr

    @property
    def available(self) -> bool:
        return self._attr_available is not False and (
            not self.entity_description.online_sensitive
            or self.coordinator.device.is_online
        )

    def get_native_value(self) -> Optional[Any]:
        """Update entity from upstream device data."""
        source = self.coordinator.device
        if (asg := self.entity_description.attribute_source) is not None:
            source = getattr(source, asg)

        if source is None:
            return None

        if (attr := self.entity_description.attribute) is None:
            return source

        return getattr(source, attr)

    def update_native_value(self) -> None:
        """Update entity from upstream device data."""
        try:
            value = self.get_native_value()

        except AttributeError as exc:
            _LOGGER.error(
                f"Critical unhandled failure while fetching "
                f"state value for entity {self}: {exc}",
                exc_info=exc,
            )
            self._attr_available = False
            return

        if value is not None:
            self._attr_available = True
            self._attr_native_value = value
        else:
            self._attr_available = False

    @final
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        ed = self.entity_description
        if (
            ed.attribute_source == "state"
            and ed.attribute is not None
            and self.coordinator.data
            and ed.attribute not in self.coordinator.data
        ):
            return
        self.update_native_value()
        self.async_write_ha_state()

    async def run_device_command(self, command: Union[str, int, CommandID]):
        d = self.coordinator.device
        if isinstance(command, str):
            command = getattr(d, command)
            if asyncio.iscoroutinefunction(command):
                result = command()
            else:
                result = self.hass.async_add_executor_job(command)
        else:
            result = d.async_remote_command(command, ensure_complete=False)

        await result


@dataclass
class PandoraCASBooleanEntityDescription(PandoraCASEntityDescription):
    icon_on: Optional[str] = None
    icon_off: Optional[str] = None
    icon_turning_on: Optional[str] = "mdi:progress-clock"
    icon_turning_off: Optional[str] = None
    flag: Optional[Flag] = None
    inverse: bool = False
    command_on: Optional[Union[int, CommandID]] = None
    command_off: Optional[Union[int, CommandID]] = None


class PandoraCASBooleanEntity(PandoraCASEntity):
    _attr_is_on: bool = False

    entity_description: PandoraCASBooleanEntityDescription

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._is_turning_on = False
        self._is_turning_off = False
        self._last_command_failed = False
        self._command_waiter: Optional[Callable[[], ...]] = None
        self._command_on_listener: Optional[Callable[[], ...]] = None
        self._command_off_listener: Optional[Callable[[], ...]] = None

    @property
    def icon(self) -> str | None:
        e = self.entity_description
        if not self.available:
            return e.icon
        if (i := e.icon_turning_on) and self._is_turning_on:
            return i
        if (i := (e.icon_turning_off or i)) and self._is_turning_off:
            return i
        if e.icon_off and not self._attr_native_value:
            return e.icon_off
        if e.icon_on and self._attr_native_value:
            return e.icon_on
        return e.icon

    async def run_binary_command(self, enable: bool) -> None:
        command_id = (
            self.entity_description.command_on
            if enable or self.entity_description.command_off is None
            else self.entity_description.command_off
        )
        if command_id is None:
            raise RuntimeError("command not defined")

        self.reset_command_event(command_id)
        self._last_command_failed = False
        if enable:
            self._is_turning_on = True
            self._is_turning_off = False
        else:
            self._is_turning_on = False
            self._is_turning_off = True
        self.async_write_ha_state()
        self._command_waiter = async_call_later(
            self.hass, 15.0, self.reset_command_event
        )

        try:
            await self.run_device_command(command_id)
        except:
            self._last_command_failed = True
            self.reset_command_event()
            raise

    def get_native_value(self) -> Optional[Any]:
        value = super().get_native_value()

        if value is None:
            return None

        if (flag := self.entity_description.flag) is not None:
            value &= flag

        return bool(value) ^ self.entity_description.inverse

    @property
    def assumed_state(self) -> bool:
        return self.entity_description.assumed_state

    @callback
    def reset_command_event(self, *_) -> None:
        self._is_turning_on = False
        self._is_turning_off = False
        if (waiter := self._command_waiter) is not None:
            waiter()
            self._command_waiter = None
        _LOGGER.debug(f"[{self}] Resetting command event")
        self.async_write_ha_state()

    @callback
    def _process_command_response(self, event: Event) -> None:
        if event.event_type != f"{DOMAIN}_command":
            return
        try:
            command_id = int(event.data[ATTR_COMMAND_ID])
        except (AttributeError, LookupError, ValueError, TypeError):
            return
        if (
            command_id != int(self.entity_description.command_on)
            and self.entity_description.command_off is not None
            and command_id != int(self.entity_description.command_off)
        ):
            return
        _LOGGER.debug(f"[{self}] Resetting command event")
        self.reset_command_event()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (on := self.entity_description.command_on) is not None:
            self._command_on_listener = self.hass.bus.async_listen(
                event_type=f"{DOMAIN}_command",
                listener=self._process_command_response,
                # event_filter={"command_id": int(on)},
            )
        if (off := self.entity_description.command_off) is not None:
            self._command_off_listener = self.hass.bus.async_listen(
                event_type=f"{DOMAIN}_command",
                listener=self._process_command_response,
                # event_filter={"command_id": int(off)},
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._command_on_listener:
            self._command_on_listener()
            self._command_on_listener = None
        if self._command_off_listener:
            self._command_off_listener()
            self._command_off_listener = None
        if self._command_waiter:
            self._command_waiter()
            self._command_waiter = None
