from typing import Final

from homeassistant.const import Platform

# Domain data
DOMAIN: Final = "pandora_cas"
PLATFORMS: Final = (
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
)

# Global data placeholders
DATA_LISTENERS: Final = DOMAIN + "_listeners"

# Configuration parameters
CONF_OFFLINE_AS_UNAVAILABLE: Final = "offline_as_unavailable"
CONF_FUEL_IS_LITERS: Final = "fuel_is_liters"
CONF_CUSTOM_CURSORS: Final = "custom_cursors"
CONF_CUSTOM_CURSOR_DEVICES: Final = "custom_cursor_devices"
CONF_CUSTOM_CURSOR_TYPE: Final = "custom_cursor_type"
CONF_MILEAGE_MILES: Final = "mileage_miles"
CONF_MILEAGE_CAN_MILES: Final = "mileage_can_miles"

DEFAULT_CURSOR_TYPE: Final = "default"
DISABLED_CURSOR_TYPE: Final = "disabled"

# Entity & event attributes
ATTR_DEVICE_ID: Final = "device_id"
ATTR_COMMAND_ID: Final = "command_id"
ATTR_GSM_LEVEL: Final = "gsm_level"
ATTR_ROTATION: Final = "rotation"
ATTR_CARDINAL: Final = "cardinal"
ATTR_KEY_NUMBER: Final = "key_number"
ATTR_TAG_NUMBER: Final = "tag_number"
ATTR_PHONE_NUMBER: Final = "phone_number"

# Home Assistant bus event identifiers
EVENT_TYPE_COMMAND: Final = f"{DOMAIN}_command"
EVENT_TYPE_EVENT: Final = f"{DOMAIN}_event"
EVENT_TYPE_POINT: Final = f"{DOMAIN}_point"
