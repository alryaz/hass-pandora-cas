import asyncio
import dataclasses
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Flag
from typing import (
    Type,
    Optional,
    Callable,
    ClassVar,
    Collection,
    Any,
    Union,
    Mapping,
    Dict,
    final,
    List,
    Awaitable,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    UpdateFailed,
)
from homeassistant.util import slugify

from custom_components.pandora_cas.api import (
    PandoraOnlineDevice,
    Features,
    CommandID,
    PandoraDeviceTypes,
    PandoraOnlineAccount,
    AuthenticationError,
    MalformedResponseError,
)
from custom_components.pandora_cas.const import (
    DOMAIN,
    ATTR_COMMAND_ID,
)

_LOGGER = logging.getLogger(__name__)


def parse_description_command_id(
    value: Any, device_type: Optional[str] = None
) -> int:
    """Retrieve command from definition."""
    if value is None:
        raise NotImplementedError("command not defined")

    if isinstance(value, Mapping):
        try:
            value = value[device_type]
        except KeyError:
            if device_type is None:
                raise NotImplementedError("command not defined")
            try:
                value = value[None]
            except KeyError:
                raise NotImplementedError("command not defined")

    return value if callable(value) else int(value)


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
    coordinator: PandoraCASUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    for device in coordinator.account.devices.values():
        # Apply filters
        for entity_description in entity_class.ENTITY_TYPES:
            if (
                (entity_description.entity_registry_enabled_default is True)
                and (features := entity_description.features) is not None
                and (device.features is None or not features & device.features)
            ):
                entity_description = dataclasses.replace(
                    entity_description,
                    entity_registry_enabled_default=False,
                )

            new_entities.append(
                entity_class(coordinator, device, entity_description)
            )

    if new_entities:
        async_add_entities(new_entities)
        logger.debug(
            f'Added {len(new_entities)} new "{platform_id.domain}" entities for account '
            f'"{entry.data[CONF_USERNAME]}": {", ".join(e.entity_id for e in new_entities)}'
        )

    return True


class PandoraCASUpdateCoordinator(
    DataUpdateCoordinator[Mapping[int, Mapping[str, Any]]]
):
    def __init__(
        self,
        hass: HomeAssistant,
        account: PandoraOnlineAccount,
    ) -> None:
        self.account = account

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5)
        )

    async def _async_update_data(self) -> Mapping[int, Mapping[str, Any]]:
        """Fetch data for sub-entities."""
        # @TODO: manual polling updates!
        try:
            try:
                updates, events = await self.account.async_request_updates()
            except AuthenticationError:
                try:
                    await self.account.async_authenticate()
                    (
                        updates,
                        events,
                    ) = await self.account.async_request_updates()
                except AuthenticationError as exc:
                    raise ConfigEntryAuthFailed(
                        "Authentication failed during fetching"
                    ) from exc
        except MalformedResponseError as exc:
            raise UpdateFailed("Malformed response retrieved") from exc

        return updates


@dataclass
class PandoraCASEntityDescription(EntityDescription):
    attribute: Optional[str] = None
    attribute_source: Optional[str] = "state"
    online_sensitive: bool = True
    features: Optional[Features] = None
    assumed_state: bool = False
    compatible_types: Collection[Union[str, None]] = (
        PandoraDeviceTypes.ALARM,
        None,
    )

    def __post_init__(self):
        """Set translation key to entity description."""
        if not self.translation_key:
            self.translation_key = self.key


CommandType = Union[CommandID, int, Callable[[PandoraOnlineDevice], Awaitable]]
CommandOptions = Union[CommandType, Mapping[str, CommandType]]


class PandoraCASEntity(CoordinatorEntity[PandoraCASUpdateCoordinator]):
    ENTITY_TYPES: ClassVar[
        Collection[PandoraCASEntityDescription]
    ] = NotImplemented
    ENTITY_ID_FORMAT: ClassVar[str] = NotImplemented

    entity_description: PandoraCASEntityDescription
    _attr_native_value: Any

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PandoraCASUpdateCoordinator,
        pandora_device: PandoraOnlineDevice,
        entity_description: "PandoraCASEntityDescription",
        extra_identifier: Any = None,
        context: Any = None,
    ) -> None:
        super().__init__(coordinator, context)
        self.pandora_device = pandora_device
        self.entity_description = entity_description

        # Set unique ID based on entity type
        unique_id = (
            f"{DOMAIN}_{pandora_device.device_id}_{entity_description.key}"
        )
        if extra_identifier is not None:
            unique_id += f"_{extra_identifier}"
        self._attr_unique_id = unique_id
        self._extra_identifier = extra_identifier

        # Generate appropriate entity ID
        entity_id = self.ENTITY_ID_FORMAT.format(
            f"{slugify(str(pandora_device.device_id))}_{slugify(entity_description.key)}"
        )
        if extra_identifier is not None:
            entity_id += "_" + slugify(str(extra_identifier))
        self.entity_id = entity_id

        # Command execution management
        self._last_command_failed = False
        self._command_waiter: Optional[Callable[[], None]] = None
        self._command_listeners: Optional[List[Callable[[], None]]] = None

        # First attributes update
        self._attr_native_value = None
        self.update_native_value()

    @property
    def device_info(self) -> DeviceInfo | None:
        d = self.pandora_device
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

        attr[ATTR_DEVICE_ID] = self.pandora_device.device_id

        return attr

    @property
    def available(self) -> bool:
        return self._attr_available is not False and (
            not self.entity_description.online_sensitive
            or self.pandora_device.is_online
        )

    def get_native_value(self) -> Optional[Any]:
        """Update entity from upstream device data."""
        source = self.pandora_device
        if (asg := self.entity_description.attribute_source) is not None:
            source = getattr(source, asg)

        if source is None:
            return None

        if (attr := self.entity_description.attribute) is None:
            return source

        return getattr(source, attr)

    def update_native_value(self) -> bool:
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
            return True

        if value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = value

        return True

    @final
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        # Do not issue update if coordinator data is empty
        if not (data := self.coordinator.data):
            return

        # Do not issue update if device id within list of data
        try:
            device_data = data[self.pandora_device.device_id]
        except KeyError:
            return

        ed = self.entity_description
        # Check whether availability can be synced to online state
        if (
            not ed.online_sensitive
            or self.available is self.pandora_device.is_online
        ):
            # Do not issue update if state attribute is involved and not set
            if (
                ed.attribute_source == "state"
                and ed.attribute is not None
                and ed.attribute not in device_data
            ):
                return

        # Update native value and write state
        if self.update_native_value():
            super()._handle_coordinator_update()

    @callback
    def reset_command_event(self) -> None:
        self._last_command_failed = False
        if (waiter := self._command_waiter) is not None:
            waiter()
            self._command_waiter = None

    @callback
    def _process_command_response(self, event: Union[Event, datetime]) -> None:
        _LOGGER.debug(f"[{self}] Resetting command event")
        self.reset_command_event()
        self.async_write_ha_state()

    def _add_command_listener(self, command: Optional[CommandOptions]) -> None:
        if command is None:
            return None
        command_id = parse_description_command_id(
            command, self.pandora_device.type
        )
        if not isinstance(command_id, int):
            return None
        if (listeners := self._command_listeners) is None:
            self._command_listeners = listeners = []
        listeners.append(
            self.hass.bus.async_listen(
                event_type=f"{DOMAIN}_command",
                listener=self._process_command_response,
                event_filter=callback(
                    lambda x: int(x.data[ATTR_COMMAND_ID]) == command_id
                ),
            )
        )

    async def run_device_command(self, command: CommandOptions):
        if command is None:
            raise ValueError("command not provided")

        # Use integer enumerations as direct command identifiers
        if isinstance(command, (int, CommandID)):
            result = self.pandora_device.async_remote_command(
                command, ensure_complete=False
            )

        # Treat callables as separate options
        elif callable(command):
            if asyncio.iscoroutinefunction(command):
                result = command(self.pandora_device)
            else:
                result = self.hass.async_add_executor_job(
                    command, self.pandora_device
                )

        else:
            raise TypeError("command type not supported")

        # Set command waiter
        if (waiter := self._command_waiter) is not None:
            waiter()
        self._command_waiter = async_call_later(
            self.hass, 15.0, self._process_command_response
        )

        # Commit current state
        self.async_write_ha_state()

        try:
            # Await command execution
            await result
        except:
            # Failed call
            self.reset_command_event()
            self._last_command_failed = True
            self.async_write_ha_state()
            raise

    async def async_will_remove_from_hass(self) -> None:
        if (waiter := self._command_waiter) is not None:
            waiter()
            self._command_waiter = None
        if listeners := self._command_listeners:
            for listener in listeners:
                listener()
            self._command_listeners = None


@dataclass
class PandoraCASBooleanEntityDescription(PandoraCASEntityDescription):
    icon_on: Optional[str] = None
    icon_off: Optional[str] = None
    icon_turning_on: Optional[str] = "mdi:progress-clock"
    icon_turning_off: Optional[str] = None
    flag: Optional[Flag] = None
    inverse: bool = False
    command_on: Optional[CommandOptions] = None
    command_off: Optional[CommandOptions] = None


class PandoraCASBooleanEntity(PandoraCASEntity):
    _attr_is_on: bool = False

    entity_description: PandoraCASBooleanEntityDescription

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._is_turning_on = False
        self._is_turning_off = False
        self._command_waiter: Optional[Callable[[], ...]] = None
        self._command_on_listener: Optional[Callable[[], ...]] = None
        self._command_off_listener: Optional[Callable[[], ...]] = None

    @property
    def icon(self) -> str | None:
        if self.available:
            e = self.entity_description
            if (i := e.icon_turning_on) and self._is_turning_on:
                return i
            if (i := (e.icon_turning_off or i)) and self._is_turning_off:
                return i
            if e.icon_off and not self._attr_native_value:
                return e.icon_off
            if e.icon_on and self._attr_native_value:
                return e.icon_on
        return super().icon

    @callback
    def reset_command_event(self) -> None:
        self._is_turning_on = False
        self._is_turning_off = False
        super().reset_command_event()

    async def run_binary_command(self, enable: bool) -> None:
        """
        Execute binary command (turn on or off).

        :param enable: Whether to run 'on' or 'off'.
        """
        # Determine command to run
        command_id = parse_description_command_id(
            (
                self.entity_description.command_on
                if enable or self.entity_description.command_off is None
                else self.entity_description.command_off
            ),
            self.pandora_device.type,
        )

        self._is_turning_on = enable
        self._is_turning_off = not enable

        await self.run_device_command(command_id)

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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._add_command_listener(self.entity_description.command_on)
        self._add_command_listener(self.entity_description.command_off)
