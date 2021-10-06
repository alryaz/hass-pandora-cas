"""Device tracker for Pandora Car Alarm System component"""
__all__ = ("async_setup_entry", "PLATFORM_DOMAIN")

import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.components.device_tracker import (
    DOMAIN as PLATFORM_DOMAIN,
    SOURCE_TYPE_GPS,
)
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from . import BasePandoraCASEntity
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

    account_object: PandoraOnlineAccount = hass.data[DOMAIN][config_entry.entry_id]

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
        _LOGGER.debug('Added device trackers for account "%s"' % (username,))
    else:
        _LOGGER.debug('Did not add any device trackers for account "%s"' % (username,))

    return True


class PandoraCASTracker(BasePandoraCASEntity, TrackerEntity):
    """Pandora Car Alarm System location tracker."""

    def __init__(self, device: PandoraOnlineDevice):
        super().__init__(device, "location_tracker")

        self._device_state = device.state

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

        self._device_state = device.state
        self._available = True

    @property
    def name(self) -> str:
        """Return device name for this tracker entity."""
        return self._device.name

    @property
    def icon(self) -> str:
        """Use vehicle icon by default."""
        return "mdi:car"

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        device_state = self._device_state
        if device_state is None:
            return 0.0
        return device_state.latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        device_state = self._device_state
        if device_state is None:
            return 0.0
        return device_state.longitude

    @property
    def source_type(self):
        """Default to GPS source only."""
        return SOURCE_TYPE_GPS

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Add some additional device attributes."""
        attributes = {}
        device_state = self._device_state

        attributes.update(super().device_state_attributes)
        if device_state is None:
            attributes.update(
                dict.fromkeys(
                    (
                        ATTR_VOLTAGE,
                        ATTR_GSM_LEVEL,
                        ATTR_DIRECTION,
                        ATTR_CARDINAL,
                        ATTR_KEY_NUMBER,
                        ATTR_TAG_NUMBER,
                    )
                )
            )
        else:
            attributes[ATTR_VOLTAGE] = device_state.voltage
            attributes[ATTR_GSM_LEVEL] = device_state.gsm_level
            attributes[ATTR_DIRECTION] = device_state.rotation
            attributes[ATTR_CARDINAL] = device_state.direction
            attributes[ATTR_KEY_NUMBER] = device_state.key_number
            attributes[ATTR_TAG_NUMBER] = device_state.tag_number

        return attributes
