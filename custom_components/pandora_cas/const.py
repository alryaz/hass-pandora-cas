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

DATA_WEB_TRANSLATIONS: Final = f"{DOMAIN}_web_translations"
DATA_WEB_TRANSLATIONS_STORE: Final = f"{DATA_WEB_TRANSLATIONS}_store"

MIN_EFFECTIVE_READ_TIMEOUT: Final = 60.0
MIN_POLLING_INTERVAL: Final = 3.0

DEFAULT_EFFECTIVE_READ_TIMEOUT: Final = 180.0
DEFAULT_POLLING_INTERVAL: Final = 6.0
DEFAULT_LANGUAGE: Final = "en"
DEFAULT_DISABLE_WEBSOCKETS: Final = False
DEFAULT_WAITER_TIMEOUT: Final = 15.0

# Configuration parameters
CONF_COORDINATES_DEBOUNCE: Final = "coordinates_debounce"
CONF_CUSTOM_CURSORS: Final = "custom_cursors"
CONF_CUSTOM_CURSOR_DEVICES: Final = "custom_cursor_devices"
CONF_CUSTOM_CURSOR_TYPE: Final = "custom_cursor_type"
CONF_DISABLE_CURSOR_ROTATION: Final = "disable_cursor_rotation"
CONF_DISABLE_WEBSOCKETS: Final = "disable_websockets"
CONF_EFFECTIVE_READ_TIMEOUT: Final = "effective_read_timeout"
CONF_ENGINE_STATE_BY_RPM: Final = "engine_state_by_rpm"
CONF_EVENT_TYPE: Final = "event_type"
CONF_FUEL_IS_LITERS: Final = "fuel_is_liters"
CONF_IGNORE_WS_COORDINATES: Final = "ignore_ws_coordinates"
CONF_MILEAGE_CAN_MILES: Final = "mileage_can_miles"
CONF_MILEAGE_MILES: Final = "mileage_miles"
CONF_OFFLINE_AS_UNAVAILABLE: Final = "offline_as_unavailable"
CONF_POLLING_INTERVAL: Final = "polling_interval"
CONF_RPM_COEFFICIENT: Final = "rpm_coefficient"
CONF_RPM_OFFSET: Final = "rpm_offset"
CONF_FORCE_LOCK_ICONS: Final = "force_lock_icons"
CONF_IGNORE_UPDATES_ENGINE_OFF: Final = "skip_updates_engine_off"

DEFAULT_COORDINATES_SMOOTHING: Final = 10.0
DEFAULT_CURSOR_TYPE: Final = "default"
DISABLED_CURSOR_TYPE: Final = "disabled"

# Entity & event attributes
ATTR_CARDINAL: Final = "cardinal"
ATTR_COMMAND_ID: Final = "command_id"
ATTR_DEVICE_ID: Final = "device_id"
ATTR_EVENT_ID_PRIMARY: Final = "event_id_primary"
ATTR_EVENT_ID_SECONDARY: Final = "event_id_secondary"
ATTR_GSM_LEVEL: Final = "gsm_level"
ATTR_KEY_NUMBER: Final = "key_number"
ATTR_PHONE_NUMBER: Final = "phone_number"
ATTR_REPLY: Final = "reply"
ATTR_RESULT: Final = "result"
ATTR_ROTATION: Final = "rotation"
ATTR_TAG_NUMBER: Final = "tag_number"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_TITLE_PRIMARY: Final = "title_primary"
ATTR_TITLE_SECONDARY: Final = "title_secondary"
ATTR_TRACK_ID: Final = "track_id"

# Home Assistant bus event identifiers
EVENT_TYPE_COMMAND: Final = DOMAIN + "_command"
EVENT_TYPE_EVENT: Final = DOMAIN + "_event"
EVENT_TYPE_POINT: Final = DOMAIN + "_point"

METHOD_COMBO: Final = "combo"
METHOD_POLL: Final = "poll"
METHOD_LISTEN: Final = "listen"
METHOD_MANUAL: Final = "manual"

ALL_METHODS: Final = (METHOD_COMBO, METHOD_LISTEN, METHOD_POLL, METHOD_MANUAL)
