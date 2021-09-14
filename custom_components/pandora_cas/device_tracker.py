"""Device tracker for BMW Connected Drive vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bmw_connected_drive/
"""
__all__ = ("async_setup_entry", "PLATFORM_DOMAIN")

import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.components.device_tracker import (
    DOMAIN as PLATFORM_DOMAIN,
    SOURCE_TYPE_GPS,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    BasePandoraCASEntity,
)
from .api import PandoraOnlineAccount, PandoraOnlineDevice
from .const import *

_LOGGER = logging.getLogger(__name__)

DEFAULT_ADD_DEVICE_TRACKER: Final = True


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_devices
):
    account_cfg = config_entry.data
    username = account_cfg[CONF_USERNAME]

    if config_entry.source == config_entries.SOURCE_IMPORT:
        account_cfg = hass.data[DATA_CONFIG][username]

    account_object: PandoraOnlineAccount = hass.data[DOMAIN][username]

    new_devices = []
    for device in account_object.devices:
        # Use default settings for device directive
        device_directive = DEFAULT_ADD_DEVICE_TRACKER

        # Skip platform directives for definitions
        platform_directive = account_cfg.get(PLATFORM_DOMAIN)
        if isinstance(platform_directive, bool):
            device_directive = platform_directive
        elif platform_directive is not None:
            device_directive = platform_directive.get(str(device.device_id))
            if device_directive is None:
                device_directive = platform_directive.get(ATTR_DEFAULT)

        # Barrier disabled device trackers
        if device_directive is False or (
            device_directive is None and not DEFAULT_ADD_DEVICE_TRACKER
        ):
            _LOGGER.debug(
                'Skipping device "%s" during platform "%s" setup'
                % (device.device_id, PLATFORM_DOMAIN)
            )
            continue

        # Add device tracker
        _LOGGER.debug(
            'Adding "%s" object to device "%s"' % (PLATFORM_DOMAIN, device.device_id)
        )
        new_devices.append(PandoraCASTracker(device))

    if new_devices:
        async_add_devices(new_devices, True)
        _LOGGER.debug(
            'Added device trackers for account "%s": %s'
            % (
                username,
                new_devices,
            )
        )
    else:
        _LOGGER.debug('Did not add any device trackers for account "%s"' % (username,))

    return True


class PandoraCASTracker(BasePandoraCASEntity, TrackerEntity):
    """Pandora Car Alarm System location tracker."""

    def __init__(self, device: PandoraOnlineDevice):
        super().__init__(device, "location_tracker")

        self._latitude = None
        self._longitude = None
        self._voltage = None
        self._gsm_level = None
        self._direction_degrees = None
        self._direction_cardinal = None

        self.entity_id = "%s.%s_%d" % (
            PLATFORM_DOMAIN,
            ".pandora_",
            self._device.device_id,
        )

    async def async_update(self):
        """Simplistic update of the device tracker."""
        device = self._device

        if not device.is_online:
            self._available = False
            return

        self._latitude = device.state.latitude
        self._longitude = device.state.longitude
        self._voltage = device.state.voltage
        self._gsm_level = device.state.gsm_level
        self._direction_degrees = device.state.rotation
        self._direction_cardinal = device.state.direction

        self._available = True

    @property
    def should_poll(self):
        """No polling for entities that have location pushed."""
        return False

    @property
    def name(self) -> str:
        """Return device name for this tracker entity."""
        return self._device.name

    @property
    def icon(self) -> str:
        """Use vehicle icon by default."""
        return "mdi:car"

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SOURCE_TYPE_GPS

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Add some additional device attributes."""
        attributes = {}
        attributes.update(super().device_state_attributes)
        attributes[ATTR_VOLTAGE] = self._voltage
        attributes[ATTR_GSM_LEVEL] = self._gsm_level
        attributes[ATTR_DIRECTION] = self._direction_degrees
        attributes[ATTR_CARDINAL] = self._direction_cardinal

        return attributes
