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
