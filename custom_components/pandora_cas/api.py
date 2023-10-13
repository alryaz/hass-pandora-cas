"""API interface for Pandora Car Alarm System."""
__all__ = [
    # Basic entities
    "PandoraOnlineAccount",
    "PandoraOnlineDevice",
    # Enumerations and flags
    "CommandID",
    "Features",
    "EventType",
    "AlertType",
    "BitStatus",
    "CurrentState",
    "BalanceState",
    "TrackingEvent",
    "TrackingPoint",
    "FuelTank",
    "PandoraDeviceTypes",
    "PrimaryEventID",
    # Exceptions
    "PandoraOnlineException",
    "AuthenticationError",
    "MalformedResponseError",
    # Constants
    "DEFAULT_USER_AGENT",
    "DEFAULT_CONTROL_TIMEOUT",
]

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Flag, IntEnum, IntFlag, auto, StrEnum
from time import time
from types import MappingProxyType
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
    Final,
    Iterable,
    Mapping,
    TypeVar,
    Union,
    SupportsFloat,
    SupportsInt,
    Optional,
    MutableMapping,
)

import aiohttp
import attr
from async_timeout import timeout

_LOGGER: Final = logging.getLogger(__name__)

#: default user agent for use in requests
DEFAULT_USER_AGENT: Final = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/60.0.3112.113 Safari/537.36"
)

#: timeout to consider command execution unsuccessful
DEFAULT_CONTROL_TIMEOUT: Final = 30


class PandoraDeviceTypes(StrEnum):
    ALARM = "alarm"
    NAV8 = "nav8"
    NAV12 = "nav12"  # @TODO: never before seen


class WSMessageType(StrEnum):
    INITIAL_STATE = "initial-state"
    STATE = "state"
    POINT = "point"
    COMMAND = "command"
    EVENT = "event"
    UPDATE_SETTINGS = "update-settings"


class CommandID(IntEnum):
    """Enumeration of possible services to be executed."""

    # Locking mechanism
    LOCK = 1
    UNLOCK = 2

    # Engine toggles
    START_ENGINE = 4
    STOP_ENGINE = 8

    # Tracking toggle
    ENABLE_TRACKING = 16
    DISABLE_TRACKING = 32

    # Active security toggle
    ENABLE_ACTIVE_SECURITY = 17
    DISABLE_ACTIVE_SECURITY = 18

    # Coolant heater toggle
    TURN_ON_BLOCK_HEATER = 21
    TURN_OFF_BLOCK_HEATER = 22

    # External (timer) channel toggle
    TURN_ON_EXT_CHANNEL = 33
    TURN_OFF_EXT_CHANNEL = 34

    # Service mode toggle
    ENABLE_SERVICE_MODE = 40  # 36?
    DISABLE_SERVICE_MODE = 41  # 37?

    # Status output toggle
    ENABLE_STATUS_OUTPUT = 48
    DISABLE_STATUS_OUTPUT = 49

    # Various commands
    TRIGGER_HORN = 23
    TRIGGER_LIGHT = 24
    TRIGGER_TRUNK = 35
    CHECK = 255

    ERASE_DTC = 57856
    READ_DTC = 57857

    # Additional commands
    ADDITIONAL_COMMAND_1 = 100
    ADDITIONAL_COMMAND_2 = 128

    # Connection toggle
    ENABLE_CONNECTION = 240
    DISABLE_CONNECTION = 15

    # NAV12-specific commands
    NAV12_DISABLE_SERVICE_MODE = 57374
    NAV12_ENABLE_SERVICE_MODE = 57375
    NAV12_TURN_OFF_BLOCK_HEATER = 57353
    NAV12_TURN_ON_BLOCK_HEATER = 57354
    NAV12_RESET_ERRORS = 57408
    NAV12_ENABLE_STATUS_OUTPUT = 57372
    NAV12_DISABLE_STATUS_OUTPUT = 57371

    # Unknown (untested and incorrectly named) commands
    STAY_HOME_PROPION = 42
    LOW_POWER_MODE = 50
    PS_CALL = 256


class EventType(IntEnum):
    """Enumeration to decode event type."""

    LOCKED = 1
    UNLOCKED = 2
    ALERT = 3
    ENGINE_STARTED = 4
    ENGINE = 5
    GEAR_CHANGE = 6
    SERVICE_MODE = 7
    SETTINGS_CHANGE = 8
    FUEL_REFILL = 9
    COLLISION = 10
    NETWORK_RECEPTION = 11
    EMERGENCY_CALL = 12
    TRUNK_OPEN_ALERT = 17
    VOLTAGE_ALERT = 19
    ACTIVE_SECURITY_ENABLED = 32
    PRE_HEATER_ENABLED = 35


class AlertType(IntEnum):
    """Enumeration to decode alert event type."""

    BATTERY = 1
    EXT_SENSOR_WARNING_ZONE = 2
    EXT_SENSOR_MAIN_ZONE = 3
    CRACK_SENSOR_WARNING_ZONE = 4
    CRACK_SENSOR_MAIN_ZONE = 5
    BRAKE_PEDAL_PRESSED = 6
    HANDBRAKE_ENGAGED = 7
    INCLINE_DETECTED = 8
    MOVEMENT_DETECTED = 9
    ENGINE_IGNITION = 10


class BitStatus(IntFlag):
    """Enumeration to decode `bit_state_1` state parameter."""

    LOCKED = pow(2, 0)
    ALARM = pow(2, 1)
    ENGINE_RUNNING = pow(2, 2)
    IGNITION = pow(2, 3)
    AUTOSTART_ACTIVE = pow(2, 4)  # AutoStart function is currently active
    HANDS_FREE_LOCKING = pow(2, 5)
    HANDS_FREE_UNLOCKING = pow(2, 6)
    GSM_ACTIVE = pow(2, 7)
    GPS_ACTIVE = pow(2, 8)
    TRACKING_ENABLED = pow(2, 9)
    ENGINE_LOCKED = pow(2, 10)
    EXT_SENSOR_ALERT_ZONE = pow(2, 11)
    EXT_SENSOR_MAIN_ZONE = pow(2, 12)
    SENSOR_ALERT_ZONE = pow(2, 13)
    SENSOR_MAIN_ZONE = pow(2, 14)
    AUTOSTART_ENABLED = pow(2, 15)  # AutoStart function is enabled
    INCOMING_SMS_ENABLED = pow(2, 16)  # Incoming SMS messages are allowed
    INCOMING_CALLS_ENABLED = pow(2, 17)  # Incoming calls are allowed
    EXTERIOR_LIGHTS_ACTIVE = pow(2, 18)  # Any exterior lights are active
    SIREN_WARNINGS_ENABLED = pow(2, 19)  # Siren warning signals disabled
    SIREN_SOUND_ENABLED = pow(2, 20)  # All siren signals disabled
    DOOR_DRIVER_OPEN = pow(2, 21)  # Door open: front left
    DOOR_PASSENGER_OPEN = pow(2, 22)  # Door open: front right
    DOOR_BACK_LEFT_OPEN = pow(2, 23)  # Door open: back left
    DOOR_BACK_RIGHT_OPEN = pow(2, 24)  # Door open: back right
    TRUNK_OPEN = pow(2, 25)  # Trunk open
    HOOD_OPEN = pow(2, 26)  # Hood open
    HANDBRAKE_ENGAGED = pow(2, 27)  # Handbrake is engaged
    BRAKES_ENGAGED = pow(2, 28)  # Pedal brake is engaged
    BLOCK_HEATER_ACTIVE = pow(2, 29)  # Pre-start heater active
    ACTIVE_SECURITY_ENABLED = pow(2, 30)  # Active security active
    BLOCK_HEATER_ENABLED = pow(2, 31)  # Pre-start heater function is available
    # ... = pow(2, 32) # ?
    EVACUATION_MODE_ACTIVE = pow(2, 33)  # Evacuation mode active
    SERVICE_MODE_ACTIVE = pow(2, 34)  # Service mode active
    STAY_HOME_ACTIVE = pow(2, 35)  # Stay home mode active
    # (...) = (pow(2, 36), ..., pow(2, 59) # ?
    SECURITY_TAGS_IGNORED = pow(2, 60)  # Ignore security tags
    SECURITY_TAGS_ENFORCED = pow(2, 61)  # Enforce security tags


class Features(Flag):
    ACTIVE_SECURITY = auto()
    AUTO_CHECK = auto()
    AUTO_START = auto()
    BEEPER = auto()
    BLUETOOTH = auto()
    EXT_CHANNEL = auto()
    NETWORK = auto()
    CUSTOM_PHONES = auto()
    EVENTS = auto()
    EXTENDED_PROPERTIES = auto()
    BLOCK_HEATER = auto()
    KEEP_ALIVE = auto()
    LIGHT_TOGGLE = auto()
    NOTIFICATIONS = auto()
    SCHEDULE = auto()
    SENSORS = auto()
    TRACKING = auto()
    TRUNK_TRIGGER = auto()
    NAV = auto()

    @classmethod
    def from_dict(cls, features_dict: dict[str, Union[bool, int]]):
        result = None
        for key, flag in {
            "active_security": cls.ACTIVE_SECURITY,
            "auto_check": cls.AUTO_CHECK,
            "autostart": cls.AUTO_START,
            "beep": cls.BEEPER,
            "bluetooth": cls.BLUETOOTH,
            "channel": cls.EXT_CHANNEL,
            "connection": cls.NETWORK,
            "custom_phones": cls.CUSTOM_PHONES,
            "events": cls.EVENTS,
            "extend_props": cls.EXTENDED_PROPERTIES,
            "heater": cls.BLOCK_HEATER,
            "keep_alive": cls.KEEP_ALIVE,
            "light": cls.LIGHT_TOGGLE,
            "notification": cls.NOTIFICATIONS,
            "schedule": cls.SCHEDULE,
            "sensors": cls.SENSORS,
            "tracking": cls.TRACKING,
            "trunk": cls.TRUNK_TRIGGER,
            "nav": cls.NAV,
        }.items():
            if key in features_dict:
                result = flag if result is None else result | flag

        return result


@attr.s(frozen=True, slots=True)
class BalanceState:
    value: float = attr.ib(converter=float)
    currency: str = attr.ib()

    def __float__(self) -> float:
        return self.value

    def __int__(self) -> int:
        return int(self.value)

    def __round__(self, n=None):
        return round(self.value, n)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any | None]):
        try:
            if data:
                return cls(
                    value=data["value"],
                    currency=data["cur"],
                )
        except (LookupError, TypeError, ValueError):
            pass


@attr.s(kw_only=True, frozen=True, slots=True)
class FuelTank:
    id: int = attr.ib()
    value: float = attr.ib()
    ras: float | None = attr.ib(default=None)
    ras_t: float | None = attr.ib(default=None)

    def __float__(self) -> float:
        return self.value

    def __int__(self) -> int:
        return int(self.value)

    def __round__(self, n=None):
        return round(self.value, n)


_T = TypeVar("_T")


def _e(x: _T) -> _T | None:
    return x or None


def _f(x: SupportsFloat | None) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        _LOGGER.warning(
            f"Could not convert value '{x}' to float, returning None"
        )
        return None


def _b(x: Any) -> bool | None:
    return None if x is None else bool(x)


def _i(x: SupportsInt | None) -> int | None:
    try:
        return None if x is None else int(x)
    except (TypeError, ValueError):
        _LOGGER.warning(
            f"Could not convert value '{x}' to int, returning None"
        )
        return None


def _degrees_to_direction(degrees: float):
    sides = (
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    )
    return sides[round(degrees / (360 / len(sides))) % len(sides)]


_TKwargs = TypeVar("_TKwargs", bound=MutableMapping[str, Any])


@attr.s(kw_only=True, frozen=True, slots=True)
class CurrentState:
    identifier: int = attr.ib(converter=int)
    is_online: bool | None = attr.ib(default=None)
    latitude: float | None = attr.ib(default=None, converter=_f)
    longitude: float | None = attr.ib(default=None, converter=_f)
    speed: float | None = attr.ib(default=None, converter=_f)
    bit_state: BitStatus | None = attr.ib(default=None)
    engine_rpm: int | None = attr.ib(default=None, converter=_i)
    engine_temperature: float | None = attr.ib(default=None, converter=_f)
    interior_temperature: float | None = attr.ib(default=None, converter=_f)
    exterior_temperature: float | None = attr.ib(default=None, converter=_f)
    fuel: float | None = attr.ib(default=None, converter=_f)
    voltage: float | None = attr.ib(default=None, converter=_f)
    gsm_level: int | None = attr.ib(default=None, converter=_i)
    balance: BalanceState | None = attr.ib(default=None)
    balance_other: BalanceState | None = attr.ib(default=None)
    mileage: float | None = attr.ib(default=None, converter=_f)
    can_mileage: float | None = attr.ib(default=None, converter=_f)
    tag_number: int | None = attr.ib(default=None, converter=_i)
    key_number: int | None = attr.ib(default=None, converter=_i)
    relay: int | None = attr.ib(default=None, converter=_i)
    is_moving: bool | None = attr.ib(default=None, converter=_b)
    is_evacuating: bool | None = attr.ib(default=None, converter=_b)
    lock_latitude: float | None = attr.ib(default=None, converter=_f)
    lock_longitude: float | None = attr.ib(default=None, converter=_f)
    rotation: float | None = attr.ib(default=None, converter=_f)
    phone: str | None = attr.ib(default=None, converter=_e)
    imei: int | None = attr.ib(default=None, converter=_e)
    phone_other: str | None = attr.ib(default=None, converter=_e)
    active_sim: int | None = attr.ib(default=None)
    tracking_remaining: float | None = attr.ib(default=None, converter=_e)

    can_seat_taken: bool | None = attr.ib(default=None)
    can_average_speed: float | None = attr.ib(default=None)
    can_consumption: float | None = attr.ib(default=None)
    can_consumption_after: float | None = attr.ib(default=None)
    can_need_pads_exchange: bool | None = attr.ib(default=None)
    can_days_to_maintenance: int | None = attr.ib(default=None)
    can_tpms_front_left: float | None = attr.ib(default=None)
    can_tpms_front_right: float | None = attr.ib(default=None)
    can_tpms_back_left: float | None = attr.ib(default=None)
    can_tpms_back_right: float | None = attr.ib(default=None)
    can_tpms_reserve: float | None = attr.ib(default=None)
    can_glass_driver: bool | None = attr.ib(default=None)
    can_glass_passenger: bool | None = attr.ib(default=None)
    can_glass_back_left: bool | None = attr.ib(default=None)
    can_glass_back_right: bool | None = attr.ib(default=None)
    can_belt_driver: bool | None = attr.ib(default=None)
    can_belt_passenger: bool | None = attr.ib(default=None)
    can_belt_back_left: bool | None = attr.ib(default=None)
    can_belt_back_right: bool | None = attr.ib(default=None)
    can_belt_back_center: bool | None = attr.ib(default=None)
    can_low_liquid: bool | None = attr.ib(default=None)
    can_mileage_by_battery: float | None = attr.ib(default=None)
    can_mileage_to_empty: float | None = attr.ib(default=None)
    can_mileage_to_maintenance: float | None = attr.ib(default=None)

    ev_state_of_charge: float | None = attr.ib(default=None)
    ev_state_of_health: float | None = attr.ib(default=None)
    ev_charging_connected: bool | None = attr.ib(default=None)
    ev_charging_slow: bool | None = attr.ib(default=None)
    ev_charging_fast: bool | None = attr.ib(default=None)
    ev_status_ready: bool | None = attr.ib(default=None)
    battery_temperature: int | None = attr.ib(default=None)

    # undecoded parameters
    smeter: int | None = attr.ib(default=None)
    tconsum: int | None = attr.ib(default=None)
    loadaxis: Any = attr.ib(default=None)
    land: int | None = attr.ib(default=None)
    bunker: int | None = attr.ib(default=None)
    ex_status: int | None = attr.ib(default=None)
    fuel_tanks: Collection[FuelTank] = attr.ib(default=())

    state_timestamp: int | None = attr.ib(default=None)
    state_timestamp_utc: int | None = attr.ib(default=None)
    online_timestamp: int | None = attr.ib(default=None)
    online_timestamp_utc: int | None = attr.ib(default=None)
    settings_timestamp_utc: int | None = attr.ib(default=None)
    command_timestamp_utc: int | None = attr.ib(default=None)

    @classmethod
    def _merge_data_kwargs(
        cls,
        data: Mapping[str, Any],
        kwargs: _TKwargs,
        to_merge: Mapping[str, str],
    ) -> _TKwargs:
        for kwarg, key in to_merge.items():
            if kwarg not in kwargs and key in data:
                kwargs[kwarg] = data[key]
        return kwargs

    @classmethod
    def get_common_dict_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
        if "identifier" not in kwargs:
            try:
                device_id = data["dev_id"]
            except KeyError:
                device_id = data["id"]
            kwargs["identifier"] = int(device_id)
        if "active_sim" not in kwargs and "active_sim" in data:
            kwargs["active_sim"] = data["active_sim"]
        if "balance" not in kwargs and "balance" in data:
            kwargs["balance"] = BalanceState.from_dict(data["balance"])
        if "balance_other" not in kwargs and "balance1" in data:
            kwargs["balance_other"] = BalanceState.from_dict(data["balance"])
        if "bit_state" not in kwargs and "bit_state_1" in data:
            kwargs["bit_state"] = BitStatus(int(data["bit_state_1"]))
        if "key_number" not in kwargs and "brelok" in data:
            kwargs["key_number"] = data["brelok"]
        if "bunker" not in kwargs and "bunker" in data:
            kwargs["bunker"] = data["bunker"]
        if "interior_temperature" not in kwargs and "cabin_temp" in data:
            kwargs["interior_temperature"] = data["cabin_temp"]
        # dtime
        # dtime_rec
        if "engine_rpm" not in kwargs and "engine_rpm" in data:
            kwargs["engine_rpm"] = data["engine_rpm"]
        if "engine_temperature" not in kwargs and "engine_temp" in data:
            kwargs["engine_temperature"] = data["engine_temp"]
        if "is_evacuating" not in kwargs and "evaq" in data:
            kwargs["is_evacuating"] = data["evaq"]
        if "ex_status" not in kwargs and "ex_status" in data:
            kwargs["ex_status"] = data["ex_status"]
        if "fuel" not in kwargs and "fuel" in data:
            kwargs["fuel"] = data["fuel"]
        # land
        # liquid_sensor
        if "gsm_level" not in kwargs and "gsm_level" in data:
            kwargs["gsm_level"] = data["gsm_level"]
        if "tag_number" not in kwargs and "metka" in data:
            kwargs["tag_number"] = data["metka"]
        if "mileage" not in kwargs and "mileage" in data:
            kwargs["mileage"] = data["mileage"]
        if "can_mileage" not in kwargs and "mileage_CAN" in data:
            kwargs["can_mileage"] = data["mileage_CAN"]
        if "is_moving" not in kwargs and "move" in data:
            kwargs["is_moving"] = data["move"]
        # online -- different on HTTP, value not timestamp
        if "exterior_temperature" not in kwargs and "out_temp" in data:
            kwargs["exterior_temperature"] = data["out_temp"]
        if "relay" not in kwargs and "relay" in data:
            kwargs["relay"] = data["relay"]
        if "rotation" not in kwargs and "rot" in data:
            kwargs["rotation"] = data["rot"]
        # smeter
        if "speed" not in kwargs and "speed" in data:
            kwargs["speed"] = data["speed"]
        # tanks -- unknown for http
        if "voltage" not in kwargs and "voltage" in data:
            kwargs["voltage"] = data["voltage"]
        if "latitude" not in kwargs and "x" in data:
            kwargs["latitude"] = data["x"]
        if "longitude" not in kwargs and "y" in data:
            kwargs["longitude"] = data["y"]
        return kwargs

    @classmethod
    def get_can_args(cls, data: Mapping[str, Any], **kwargs) -> dict[str, Any]:
        return cls._merge_data_kwargs(
            data,
            kwargs,
            {
                # Tire pressure
                "can_tpms_front_left": "CAN_TMPS_forvard_left",
                "can_tpms_front_right": "CAN_TMPS_forvard_right",
                "can_tpms_back_left": "CAN_TMPS_back_left",
                "can_tpms_back_right": "CAN_TMPS_back_right",
                "can_tpms_reserve": "CAN_TMPS_reserve",
                # Glasses
                "can_glass_driver": "CAN_driver_glass",
                "can_glass_passenger": "CAN_passenger_glass",
                "can_glass_back_left": "CAN_back_left_glass",
                "can_glass_back_right": "CAN_back_right_glass",
                # Belts
                "can_belt_driver": "CAN_driver_belt",
                "can_belt_passenger": "CAN_passenger_belt",
                "can_belt_back_left": "CAN_back_left_belt",
                "can_belt_back_right": "CAN_back_right_belt",
                "can_belt_back_center": "CAN_back_center_belt",
                # Mileages (non-generic)
                "can_mileage_by_battery": "CAN_mileage_by_battery",
                "can_mileage_to_empty": "CAN_mileage_to_empty",
                "can_mileage_to_maintenance": "CAN_mileage_to_maintenance",
                # EV-related
                "ev_charging_connected": "charging_connect",
                "ev_charging_slow": "charging_slow",
                "ev_charging_fast": "charging_fast",
                "ev_state_of_charge": "SOC",
                "ev_state_of_health": "SOH",
                "ev_status_ready": "ev_status_ready",
                "battery_temperature": "battery_temperature",
                # Miscellaneous
                "can_average_speed": "CAN_average_speed",
                "can_low_liquid": "CAN_low_liquid",
                "can_seat_taken": "CAN_seat_taken",
                "can_consumption": "CAN_consumption",
                "can_consumption_after": "CAN_consumption_after",
                "can_need_pads_exchange": "CAN_need_pads_exchange",
                "can_days_to_maintenance": "CAN_days_to_maintenance",
            },
        )

    @classmethod
    def get_ws_state_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
        if "is_online" not in kwargs and "online_mode" in data:
            kwargs["is_online"] = bool(data["online_mode"])
        if "lock_latitude" not in kwargs and "lock_x" in data:
            if (lock_x := data["lock_x"]) is not None:
                lock_x = float(lock_x) / 1000000
            kwargs["lock_latitude"] = lock_x
        if "lock_longitude" not in kwargs and "lock_y" in data:
            if (lock_y := data["lock_y"]) is not None:
                lock_y = float(lock_y) / 1000000
            kwargs["lock_longitude"] = lock_y / 1000000
        # if "tanks" in data:
        #     kwargs["fuel_tanks"] = FuelTank.parse_fuel_tanks(data["tanks"])
        return cls._merge_data_kwargs(
            data,
            cls.get_common_dict_args(data, **cls.get_can_args(data, **kwargs)),
            {
                "state_timestamp": "state",
                "state_timestamp_utc": "state_utc",
                "online_timestamp": "online",
                "online_timestamp_utc": "online_utc",
                "settings_timestamp_utc": "setting_utc",
                "command_timestamp_utc": "command_utc",
                "active_sim": "active_sim",
                "tracking_remaining": "track_remains",
            },
        )

    @classmethod
    def get_ws_point_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
        # flags ...
        # max_speed ...
        # timezone ...
        # Lbs_coords ...
        return cls.get_common_dict_args(data, **kwargs)

    @classmethod
    def get_http_dict_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
        # parse CAN data if present
        if can := data.get("can"):
            kwargs = cls.get_can_args(can, **kwargs)
        return cls.get_common_dict_args(data, **kwargs)

    @property
    def direction(self) -> str:
        """Textual interpretation of rotation."""
        return _degrees_to_direction(self.rotation or 0.0)


class PrimaryEventID(IntEnum):
    UNKNOWN = 0
    LOCKING_ENABLED = 1
    LOCKING_DISABLED = 2
    ALERT = 3
    ENGINE_STARTED = 4
    ENGINE_STOPPED = 5
    ENGINE_LOCKED = 6
    SERVICE_MODE_ENABLED = 7
    SETTINGS_CHANGED = 8
    REFUEL = 9
    COLLISION = 10
    GSM_CONNECTION = 11
    EMERGENCY_CALL = 12
    FAILED_START_ATTEMPT = 13
    TRACKING_ENABLED = 14
    TRACKING_DISABLED = 15
    SYSTEM_POWER_LOSS = 16
    SECURE_TRUNK_OPEN = 17
    FACTORY_TESTING = 18
    POWER_DIP = 19
    CHECK_RECEIVED = 20
    SYSTEM_LOGIN = 29
    ACTIVE_SECURITY_ENABLED = 32
    ACTIVE_SECURITY_DISABLED = 33
    ACTIVE_SECURITY_ALERT = 34
    BLOCK_HEATER_ENABLED = 35
    BLOCK_HEATER_DISABLED = 36
    ROUGH_ROAD_CONDITIONS = 37
    DRIVING = 38
    ENGINE_RUNNING_PROLONGATION = 40
    SERVICE_MODE_DISABLED = 41
    GSM_CHANNEL_ENABLED = 42
    GSM_CHANNEL_DISABLED = 43
    NAV_11_STATUS = 48
    DTC_READ_REQUEST = 166
    DTC_READ_ERROR = 167
    DTC_READ_ACTIVE = 168
    DTC_ERASE_REQUEST = 169
    DTC_ERASE_ACTIVE = 170
    SYSTEM_MESSAGE = 176
    ECO_MODE_ENABLED = 177
    ECO_MODE_DISABLED = 178
    TIRE_PRESSURE_LOW = 179
    BLUETOOTH_STATUS = 220
    TAG_REQUIREMENT_ENABLED = 230
    TAG_REQUIREMENT_DISABLED = 231
    TAG_POLLING_ENABLED = 232
    TAG_POLLING_DISABLED = 233
    POINT = 250

    @classmethod
    def _missing_(cls, value: object) -> Any:
        return cls.UNKNOWN


@attr.s(kw_only=True, frozen=True, slots=True)
class TrackingEvent:
    identifier: int = attr.ib()
    device_id: int = attr.ib()
    bit_state: BitStatus = attr.ib()
    cabin_temperature: float = attr.ib()
    engine_rpm: float = attr.ib()
    engine_temperature: float = attr.ib()
    event_id_primary: int = attr.ib()
    event_id_secondary: int = attr.ib()
    fuel: int = attr.ib()
    gsm_level: int = attr.ib()
    exterior_temperature: int = attr.ib()
    voltage: float = attr.ib()
    latitude: float = attr.ib()
    longitude: float = attr.ib()
    timestamp: int = attr.ib()
    recorded_timestamp: int = attr.ib()

    @property
    def primary_event_enum(self) -> PrimaryEventID:
        return PrimaryEventID(self.event_id_primary)

    @classmethod
    def get_dict_args(cls, data: Mapping[str, Any], **kwargs):
        if "identifier" not in kwargs:
            kwargs["identifier"] = int(data["id"])
        if "device_id" not in kwargs:
            kwargs["device_id"] = int(data["dev_id"])
        if "bit_state" not in kwargs:
            kwargs["bit_state"] = BitStatus(int(data["bit_state_1"]))
        if "cabin_temperature" not in kwargs:
            kwargs["cabin_temperature"] = data["cabin_temp"]
        if "engine_rpm" not in kwargs:
            kwargs["engine_rpm"] = data["engine_rpm"]
        if "engine_temperature" not in kwargs:
            kwargs["engine_temperature"] = data["engine_temp"]
        if "event_id_primary" not in kwargs:
            kwargs["event_id_primary"] = data["eventid1"]
        if "event_id_secondary" not in kwargs:
            kwargs["event_id_secondary"] = data["eventid2"]
        if "fuel" not in kwargs:
            kwargs["fuel"] = data["fuel"]
        if "gsm_level" not in kwargs:
            kwargs["gsm_level"] = data["gsm_level"]
        if "exterior_temperature" not in kwargs:
            kwargs["exterior_temperature"] = data["out_temp"]
        if "timestamp" not in kwargs:
            try:
                timestamp = data["dtime"]
            except KeyError:
                timestamp = data["time"]
            kwargs["timestamp"] = timestamp
        if "recorded_timestamp" not in kwargs:
            kwargs["recorded_timestamp"] = data["dtime_rec"]
        if "voltage" not in kwargs:
            kwargs["voltage"] = data["voltage"]
        if "latitude" not in kwargs:
            kwargs["latitude"] = data["x"]
        if "longitude" not in kwargs:
            kwargs["longitude"] = data["y"]
        return kwargs

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], **kwargs):
        return cls(**cls.get_dict_args(data, **kwargs))


@attr.s(kw_only=True, frozen=True, slots=True)
class TrackingPoint:
    device_id: int = attr.ib()
    latitude: float = attr.ib()
    longitude: float = attr.ib()
    track_id: int | None = attr.ib(default=None)
    timestamp: float = attr.ib(default=time)
    fuel: int | None = attr.ib(default=None)
    speed: float | None = attr.ib(default=None)
    max_speed: float | None = attr.ib(default=None)
    length: float | None = attr.ib(default=None)


class PandoraOnlineAccount:
    """Pandora Online account interface."""

    BASE_URL = "https://pro.p-on.ru"

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        access_token: str | None = None,
        utc_offset: int = 0,
        *,
        logger: (
            logging.Logger
            | logging.LoggerAdapter
            | type[logging.LoggerAdapter]
        ) = _LOGGER,
    ) -> None:
        """
        Instantiate Pandora Online account object.
        :param username: Account username
        :param password: Account password
        :param access_token: Access token (optional)
        """
        if utc_offset is None:
            from calendar import timegm
            from time import mktime, localtime, gmtime

            utc_offset = timegm(t := localtime()) - timegm(gmtime(mktime(t)))

        if not (-86400 < utc_offset < 86400):
            raise ValueError("utc offset cannot be greater than 24 hours")

        self._utc_offset = utc_offset
        self._username = username
        self._password = password
        self.access_token = access_token
        self._user_id: int | None = None
        self._session = session

        #: last update timestamp
        self._last_update = -1

        #: list of vehicles associated with this account.
        self._devices: dict[int, PandoraOnlineDevice] = {}

        if isinstance(logger, type):
            logger = logger(_LOGGER)
        self.logger = logger

    def __repr__(self):
        """Retrieve representation of account object"""
        return f"<{self}>"

    def __str__(self):
        return (
            f"{self.__class__.__name__}["
            f'username="{self.username}", '
            f"user_id={self.user_id}"
            f"]"
        )

    # Basic properties
    @property
    def utc_offset(self) -> int:
        return self._utc_offset

    @property
    def user_id(self) -> int | None:
        return self._user_id

    @property
    def username(self) -> str:
        """Username accessor."""
        return self._username

    @property
    def last_update(self) -> int:
        return self._last_update

    @property
    def devices(self) -> Mapping[int, "PandoraOnlineDevice"]:
        """Devices (immutable) accessor."""
        return MappingProxyType(self._devices)

    # Requests
    @staticmethod
    async def _handle_json_response(response: aiohttp.ClientResponse) -> Any:
        """
        Process aiohttp response into data decoded from JSON.

        :param response: aiohttp.ClientResponse object.
        :return: Decoded JSON data.
        :raises PandoraOnlineException: Bad status, but server described it.
        :raises MalformedResponseError: When bad JSON message encountered.
        :raises aiohttp.ClientResponseError: When unexpected response status.
        """
        given_exc, data = None, None
        try:
            data = await response.json(content_type=None)
        except json.JSONDecodeError as e:
            given_exc = MalformedResponseError("bad JSON encoding")
            given_exc.__cause__ = e
            given_exc.__context__ = e
        # else:
        #     # When making a pull request, make sure not to remove this section.
        #     _LOGGER.debug(f"{response.method} {response.url.path} < {data}")

        try:
            status = (
                data.get("error_text")
                or data.get("status")
                or data.get("action_result")
            )
        except AttributeError:
            status = None

        if 400 <= response.status <= 403:
            raise AuthenticationError(status or "unknown auth error")

        try:
            # Raise for status at this point
            response.raise_for_status()
        except aiohttp.ClientResponseError as exc:
            if status is not None:
                raise PandoraOnlineException(status) from exc
            raise

        # Raise exception for encoding if presented previously
        if given_exc:
            raise given_exc

        # Return data ready for consumption
        return data

    @staticmethod
    async def _handle_dict_response(response: aiohttp.ClientResponse) -> dict:
        """Process aiohttp response into a dictionary decoded from JSON."""
        data = await PandoraOnlineAccount._handle_json_response(response)
        if not isinstance(data, dict):
            raise MalformedResponseError("response is not a mapping")
        return data

    @staticmethod
    async def _handle_list_response(response: aiohttp.ClientResponse) -> list:
        """Process aiohttp response into a list decoded from JSON."""
        data = await PandoraOnlineAccount._handle_json_response(response)
        if not isinstance(data, list):
            raise MalformedResponseError("response is not a list")
        return data

    async def async_check_access_token(
        self, access_token: str | None = None
    ) -> None:
        """
        Validate access token against API.

        :param access_token: Check given access token. When none provided,
                             current access token is checked.
        :raises MalformedResponseError: Response payload is malformed.
        :raises MissingAccessTokenError: No token is provided or present.
        :raises SessionExpiredError: Token expired or never authed.
        :raises InvalidAccessTokenError: Malformed token is provided.
        :raises AuthenticationException: All other auth-related errors.
        """

        # Extrapolate access token to use within request
        if not (access_token or (access_token := self.access_token)):
            raise MissingAccessTokenError("access token not available")

        # Perform request
        async with self._session.post(
            self.BASE_URL + "/api/iamalive",
            data={"access_token": access_token},
        ) as request:
            # Accept all successful requests, do not check payload
            if request.status == 200:
                return

            # Decode payload for errors
            try:
                response = await request.json(content_type=None)
            except json.JSONDecodeError as e:
                self.logger.error(
                    f"Malformed access token checking "
                    f"response: {await response.text()}",
                    exc_info=e,
                )
                raise MalformedResponseError("Malformed checking response")

        self.logger.debug(f"Received error for access token check: {response}")

        # Extract status code (description) from payload
        try:
            status = response["status"]
        except (AttributeError, LookupError):
            raise AuthenticationError("error contains no status")

        # Custom exceptions for certain status codes
        if "expired" in status:
            raise SessionExpiredError(status)
        if "wrong" in status:
            raise InvalidAccessTokenError(status)

        # Raise for all other status codes
        raise AuthenticationError(status)

    async def async_fetch_access_token(self) -> str:
        """
        Retrieve new access token from server.
        :returns: New access token
        :raises MalformedResponseError: Response payload is malformed.
        """
        async with self._session.post(
            self.BASE_URL + "/oauth/token",
            headers={
                "Authorization": "Basic cGNvbm5lY3Q6SW5mXzRlUm05X2ZfaEhnVl9zNg==",
            },
        ) as response:
            data = await self._handle_dict_response(response)

            try:
                return data["access_token"]
            except KeyError as e:
                raise MalformedResponseError("Access token not present") from e

    async def async_apply_access_token(self, access_token: str):
        """
        Attempt authentication using provided access token.
        :param access_token: Access token for authentication
        :raises MalformedResponseError: Issues related to user ID
        """
        self.logger.debug(f"Authenticating access token: {access_token}")

        async with self._session.post(
            self.BASE_URL + "/api/users/login",
            data={
                "login": self._username,
                "password": self._password,
                "lang": "ru",
                "v": "3",
                "utc_offset": self._utc_offset // 60,
                "access_token": access_token,
            },
        ) as response:
            try:
                data = await self._handle_dict_response(response)
            except AuthenticationError:
                raise
            except PandoraOnlineException as exc:
                raise AuthenticationError(*exc.args) from exc

        # Extrapolate user identifier
        try:
            user_id = int(data["user_id"])
        except (TypeError, ValueError) as exc:
            raise MalformedResponseError("Unexpected user ID format") from exc
        except KeyError as exc:
            raise MalformedResponseError("User ID not present") from exc

        # Save processed data
        self._user_id = user_id
        self.access_token = access_token

        self.logger.info("Access token authentication successful")

    async def async_authenticate(
        self, access_token: str | None = None
    ) -> None:
        """
        Perform authentication (optionally using provided access token).

        Performs authentication in 4 steps at max:
        - Attempt authentication using provided token
        - Attempt authentication using existing token
        - Attempt fetching new access token
        - Attempt authentication using new token

        At most three different access tokens may circulate within
        this method.

        Raises all exceptions from `async_fetch_access_token` and
        `async_apply_access_token`.
        :param access_token: Optional access token to use.
        :raises MalformedResponseError: Issues related to user ID.
        """
        self.logger.debug(f"Authenticating access token: {access_token}")
        if access_token:
            try:
                await self.async_apply_access_token(access_token)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning(
                    f"Authentication with provided access token failed: {exc}",
                    exc_info=exc,
                )
            else:
                return

        if (
            access_token != (access_token := self.access_token)
            and access_token
        ):
            try:
                await self.async_apply_access_token(access_token)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning(
                    f"Authentication with existing access token failed: {exc}",
                    exc_info=exc,
                )
            else:
                return

        try:
            access_token = await self.async_fetch_access_token()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.error(
                f"Could not retrieve access token: {exc}",
                exc_info=exc,
            )
            raise

        try:
            await self.async_apply_access_token(access_token)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            self.logger.error(
                f"Authentication with fetched access token failed: {exc}",
                exc_info=exc,
            )
            raise

    async def async_refresh_devices(self) -> None:
        """
        Retrieve and cache list of vehicles for the account.

        :raises MissingAccessTokenError: No access token for request.
        :raises MalformedResponseError: Device data is malformed beyond reading.
        :raises aiohttp.ClientError: Error requesting data.
        """
        if not (access_token := self.access_token):
            raise MissingAccessTokenError

        self.logger.debug("Retrieving devices")

        async with self._session.get(
            self.BASE_URL + "/api/devices",
            params={"access_token": access_token},
        ) as response:
            devices_data = await self._handle_list_response(response)

        self.logger.debug(f"Retrieved devices: {devices_data}")

        for device_attributes in devices_data:
            try:
                device_id = self.parse_device_id(device_attributes)
            except (TypeError, ValueError, LookupError) as exc:
                self.logger.error(
                    f"Error parsing device ID: {exc}", exc_info=exc
                )
            else:
                try:
                    device_object = self._devices[device_id]
                except LookupError:
                    self.logger.debug(f"Adding new device with ID {device_id}")
                    self._devices[device_id] = PandoraOnlineDevice(
                        self, device_attributes, logger=self.logger
                    )
                else:
                    device_object.attributes = device_attributes

    async def async_remote_command(
        self, device_id: int, command_id: int | CommandID
    ) -> None:
        """
        Execute remote command on target device.
        :param device_id: Device ID to execute command on.
        :param command_id: Identifier of the command to execute.
        :raises PandoraOnlineException: Failed command execution with response.
        """
        self.logger.info(f"Sending command {command_id} to device {device_id}")

        async with self._session.post(
            self.BASE_URL + "/api/devices/command",
            data={"id": device_id, "command": int(command_id)},
            params={"access_token": self.access_token},
        ) as response:
            data = await self._handle_dict_response(response)

        try:
            status = data["action_result"][str(device_id)]
        except (LookupError, AttributeError, TypeError):
            status = "unknown error"

        if status != "sent":
            self.logger.error(
                f"Error sending command {command_id} "
                f"to device {device_id}: {status}"
            )
            raise PandoraOnlineException(status)

        self.logger.info(f"Command {command_id} sent to device {device_id}")

    async def async_wake_up_device(self, device_id: int) -> None:
        """
        Send wake up command to target device.

        :param device_id: Device identifier
        """
        self.logger.info(f"Waking up device {device_id}")

        async with self._session.post(
            self.BASE_URL + "/api/devices/wakeup",
            data={"id": device_id},
            params={"access_token": self.access_token},
        ) as response:
            data = await self._handle_dict_response(response)

        try:
            status = data["status"]
        except (LookupError, AttributeError, TypeError):
            status = "unknown error"

        if status != "success":
            self.logger.error(f"Error waking up device {device_id}: {status}")
            raise PandoraOnlineException(status)

        response.raise_for_status()

    async def async_fetch_device_settings(
        self, device_id: int | str
    ) -> dict[str, Any]:
        """
        Fetch settings relevant to target device.

        :param device_id: Device identifier
        """
        async with self._session.get(
            self.BASE_URL + "/api/devices/settings",
            params={"access_token": self.access_token, "id": device_id},
        ) as response:
            data = await self._handle_dict_response(response)

        try:
            devices_settings = data["device_settings"]
        except KeyError as exc:
            raise MalformedResponseError(
                "device_settings not retrieved"
            ) from exc

        if not (device_id is None or device_id in devices_settings):
            raise MalformedResponseError("settings not retrieved")

        return sorted(
            devices_settings[device_id], key=lambda x: x.get("dtime") or 0
        )[-1]

    @staticmethod
    def parse_device_id(data: Mapping[str, Any]) -> int:
        # Fixes absense of identifier value on certain device responses.
        try:
            device_id = data["dev_id"]
        except KeyError:
            device_id = data["id"]

        if not device_id:
            raise ValueError("device ID is empty / zero")

        return int(device_id)

    @staticmethod
    def parse_fuel_tanks(
        fuel_tanks_data: Iterable[Mapping[str, Any | None]],
        existing_fuel_tanks: Collection[FuelTank | None] = None,
    ) -> tuple[FuelTank, ...]:
        fuel_tanks = []

        for fuel_tank_data in fuel_tanks_data or ():
            id_ = int(fuel_tank_data["id"])

            fuel_tank = None

            for existing_fuel_tank in existing_fuel_tanks or ():
                if existing_fuel_tank.id == id_:
                    fuel_tank = existing_fuel_tank
                    break

            try:
                ras = float(fuel_tank_data["ras"])
            except (ValueError, TypeError, LookupError):
                ras = None

            try:
                ras_t = float(fuel_tank_data["ras_t"])
            except (ValueError, TypeError, LookupError):
                ras_t = None

            try:
                value = float(fuel_tank_data["val"])
            except (ValueError, TypeError, LookupError):
                value = 0.0

            if fuel_tank is None:
                fuel_tanks.append(
                    FuelTank(id=id_, value=value, ras=ras, ras_t=ras_t)
                )
            else:
                object.__setattr__(fuel_tank, "value", value)
                object.__setattr__(fuel_tank, "ras", ras)
                object.__setattr__(fuel_tank, "ras_t", ras_t)

        return tuple(fuel_tanks)

    def _update_device_current_state(
        self, device: "PandoraOnlineDevice", **state_args
    ) -> tuple[CurrentState, dict[str, Any]]:
        # Extract UTC offset
        prefixes = ("online", "state")
        utc_offset = device.utc_offset
        for prefix in prefixes:
            utc = (non_utc := prefix + "_timestamp") + "_utc"
            if not (
                (non_utc_val := state_args.get(non_utc)) is None
                or (utc_val := state_args.get(utc)) is None
            ):
                utc_offset = round((non_utc_val - utc_val) / 60) * 60
                if device.utc_offset != utc_offset:
                    self.logger.debug(
                        f"Calculated UTC offset for device {device.device_id}: {utc_offset} seconds"
                    )
                    device.utc_offset = utc_offset
                break

        # Adjust for two timestamps
        for prefix in prefixes:
            utc = (non_utc := prefix + "_timestamp") + "_utc"
            if (val := state_args.get(utc)) is not None:
                if state_args.get(non_utc) is None:
                    state_args[non_utc] = val + utc_offset
            elif (val := state_args.get(non_utc)) is not None:
                state_args[utc] = val - utc_offset

        # Create new state if not present
        if (state := device.state) is None:
            device.state = state = CurrentState(**state_args)
            self.logger.debug(
                f"Setting new state object on device {device.device_id}"
            )
        else:
            bad_timestamp = None
            for postfix in ("", "_utc"):
                for prefix in prefixes:
                    if (
                        getattr(
                            state, key := (prefix + "_timestamp" + postfix)
                        )
                        is None
                    ):
                        continue
                    if state_args.get(key) is None:
                        continue
                    if getattr(state, key) <= state_args.get(key):
                        continue
                    bad_timestamp = key
                    break
            if bad_timestamp is None:
                device.state = attr.evolve(state, **state_args)
                self.logger.debug(
                    f"Updating state object on device {device.device_id}"
                )
            else:
                self.logger.warning(
                    f"State update for device {device.device_id} is "
                    f"older than existing data (based on '{bad_timestamp}'), "
                    f"this state update will be ignored completely!"
                )
                for postfix in ("", "_utc"):
                    for prefix in prefixes:
                        key = f"{prefix}_timestamp{postfix}"
                        cur, new = (
                            getattr(state, key) or 0,
                            state_args.get(key) or 0,
                        )
                        sign = (
                            "=" if cur == new else ("<" if cur < new else ">")
                        )
                        self.logger.debug(
                            f"Timestamp {key} for {device.device_id}: {cur} {sign} {new}"
                        )
                return state, {}

        # noinspection PyTypeChecker
        return state, state_args

    def _process_http_event(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> TrackingEvent:
        event = TrackingEvent.from_dict(data, device_id=device.device_id)

        if (e := device.last_event) and e.timestamp < event.timestamp:
            device.last_event = TrackingEvent

        return event

    def _process_http_state(
        self,
        device: "PandoraOnlineDevice",
        data_stats: Mapping[str, Any] | None = None,
        data_time: Mapping[str, Any] | None = None,
    ) -> tuple[CurrentState, dict[str, Any]]:
        update_args = {}
        if data_stats:
            self.logger.debug(
                f"Received data update from HTTP for device {device.device_id}: {data_stats}"
            )
            update_args.update(
                **CurrentState.get_common_dict_args(
                    data_stats,
                    identifier=device.device_id,
                ),
                is_online=bool(data_stats.get("online")),
            )
        if data_time:
            self.logger.debug(
                f"Received time update from HTTP for device {device.device_id}: {data_time}"
            )
            update_args.update(
                online_timestamp=data_time.get("onlined"),
                online_timestamp_utc=data_time.get("online"),
                command_timestamp_utc=data_time.get("command"),
                settings_timestamp_utc=data_time.get("setting"),
            )
        return self._update_device_current_state(device, **update_args)

    async def async_fetch_events(
        self,
        timestamp_from: int = 0,
        timestamp_to: int | None = None,
        limit: int = 20,
        device_id: int | None = None,
    ) -> list[TrackingEvent]:
        if timestamp_from < 0:
            raise ValueError("timestamp_from must not be less than zero")
        if timestamp_to is None:
            # Request future to avoid timezone differences
            timestamp_to = int(
                (datetime.now() + timedelta(days=1)).timestamp()
            )

        log_postfix = f"between {timestamp_from} and {timestamp_to}"
        self.logger.debug(f"Fetching events{log_postfix}")
        params = {
            "access_token": self.access_token,
            "from": str(timestamp_from),
            "to": str(timestamp_to),
        }
        if device_id:
            params["id"] = str(device_id)
        if limit:
            params["limit"] = str(limit)
        async with self._session.get(
            self.BASE_URL + "/api/lenta",
            params=params,
        ) as response:
            data = await self._handle_dict_response(response)

        events = []
        for event_entry in data.get("lenta") or []:
            if not (event_data := event_entry.get("obj")):
                continue
            events.append(TrackingEvent.from_dict(event_data))
        self.logger.debug(f"Received {len(events)} event{log_postfix}")
        return events

    async def async_request_updates(
        self, timestamp: int | None = None
    ) -> tuple[dict[int, dict[str, Any]], list[TrackingEvent]]:
        """
        Fetch the latest changes from update server.
        :param timestamp: Timestamp to fetch updates since (optional, uses
                          last update timestamp internally if not provided).
        :return: Dictionary of (device_id => (state_attribute => new_value))
        """
        if not (access_token := self.access_token):
            raise MissingAccessTokenError("Account is not authenticated")

        # Select last timestamp if none provided
        _timestamp = self._last_update if timestamp is None else timestamp

        self.logger.info(f"Fetching changes since {_timestamp}")

        async with self._session.get(
            self.BASE_URL + "/api/updates",
            params={"ts": _timestamp, "access_token": access_token},
        ) as response:
            data = await self._handle_dict_response(response)

        device_new_attrs: dict[int, dict[str, Any]] = {}

        # Stats / time updates
        updates: dict[int, dict[str, dict[str, Any]]] = {}
        for key in ("stats", "time"):
            # Check if response contains necessary data
            if not (mapping := data.get(key)):
                continue

            # Iterate over device responses
            for device_id, device_data in mapping.items():
                try:
                    device = self._devices[int(device_id)]
                except (TypeError, ValueError):
                    self.logger.warning(
                        f"Bad device ID in {key} data: {device_id}"
                    )
                except LookupError:
                    self.logger.warning(
                        f"Received {key} data for "
                        f"uninitialized device {device_id}: {device_data}"
                    )
                    continue
                else:
                    # Two .setdefault-s just in case data is doubled
                    updates.setdefault(device.device_id, {}).setdefault(
                        "data_" + key, {}
                    ).update(device_data)

        # Process state update once the list has been compiled
        for device_id, update_args in updates.items():
            device_new_attrs[device_id] = self._process_http_state(
                self._devices[device_id], **update_args
            )[1]

        # Event updates
        events = []
        for event_wrapper in data.get("lenta") or ():
            if not (event_obj := event_wrapper.get("obj")):
                continue

            try:
                raw_device_id = event_obj["dev_id"]
            except (LookupError, AttributeError):
                # @TODO: handle such events?
                continue

            try:
                device = self._devices[int(raw_device_id)]
            except (TypeError, ValueError):
                self.logger.warning(
                    f"Bad device ID in event data: {raw_device_id}"
                )
                continue
            except LookupError:
                self.logger.warning(
                    "Received event data for "
                    f"uninitialized device {raw_device_id}: {event_obj}"
                )
                continue

            events.append(self._process_ws_event(device, event_obj))

        if device_new_attrs:
            self.logger.debug(
                f"Received updates from HTTP: {device_new_attrs}"
            )

        try:
            self._last_update = int(data["ts"])
        except (LookupError, TypeError, ValueError):
            self.logger.warning("Response did not contain timestamp")

        return device_new_attrs, events

    def _process_ws_initial_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> tuple[CurrentState, dict[str, Any]]:
        """
        Process WebSockets state initialization.
        :param device: Device this update is designated for
        :param data: Data containing update
        :return: [Device state, Dictionary of real updates]
        """

        self.logger.debug(
            f"Initializing state for {device.device_id} from {data}"
        )

        return self._update_device_current_state(
            device,
            **CurrentState.get_ws_state_args(
                data, identifier=device.device_id
            ),
        )

    def _process_ws_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> tuple[CurrentState, dict[str, Any]]:
        """
        Process WebSockets state update.
        :param device: Device this update is designated for
        :param data: Data containing update
        :return: [Device state, Dictionary of real updates]
        """
        self.logger.debug(f"Updating state for {device.device_id}")

        return self._update_device_current_state(
            device,
            **CurrentState.get_ws_state_args(
                data, identifier=device.device_id
            ),
        )

    # The routines are virtually the same
    _process_ws_event = _process_http_event

    def _process_ws_point(
        self,
        device: "PandoraOnlineDevice",
        data: Mapping[str, Any],
    ) -> tuple[TrackingPoint, CurrentState | None, dict[str, Any] | None]:
        try:
            fuel = data["fuel"]
        except KeyError:
            fuel = None
        else:
            if fuel is not None:
                fuel = float(fuel)

        try:
            speed = data["speed"]
        except KeyError:
            speed = None
        else:
            if speed is not None:
                speed = float(speed)

        try:
            max_speed = data["max_speed"]
        except KeyError:
            max_speed = None
        else:
            if max_speed is not None:
                max_speed = float(max_speed)

        try:
            length = data["length"]
        except KeyError:
            length = None
        else:
            if length is not None:
                length = float(length)

        timestamp = data.get("dtime") or time()

        # Update state since point is newer
        if (state := device.state) and state.state_timestamp <= timestamp:
            state, state_args = self._update_device_current_state(
                device,
                **CurrentState.get_ws_point_args(
                    data,
                    identifier=device.device_id,
                    state_timestamp=timestamp,
                ),
            )
        else:
            state_args = None

        return (
            TrackingPoint(
                device_id=device.device_id,
                track_id=data["track_id"],
                latitude=data["x"],
                longitude=data["y"],
                timestamp=timestamp,
                fuel=fuel,
                speed=speed,
                max_speed=max_speed,
                length=length,
            ),
            state,
            state_args,
        )

    # noinspection PyMethodMayBeStatic
    def _process_ws_command(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> tuple[int, int, int]:
        command_id, result, reply = (
            data["command"],
            data["result"],
            data["reply"],
        )

        if device.control_busy:
            if result:
                device.release_control_lock()
            else:
                device.release_control_lock(f"(CID:{command_id}) {reply}")

        return command_id, result, reply

    # noinspection PyMethodMayBeStatic
    def _process_ws_update_settings(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # @TODO: do something?
        return {
            **data,
            "device_id": device.device_id,
        }

    async def _do_ws_auto_auth(self) -> bool:
        try:
            try:
                self.logger.debug("[reauth] Checking WS access token")
                await self.async_check_access_token()
            except AuthenticationError:
                self.logger.debug("[reauth] Performing authentication")
                await self.async_authenticate()
            else:
                self.logger.debug("[reauth] WS access token still valid")
        except asyncio.CancelledError:
            raise
        except AuthenticationError as exc:
            self.logger.error(
                f"[reauth] Severe authentication error: {exc}",
                exc_info=exc,
            )
            raise
        except (OSError, TimeoutError) as exc:
            self.logger.error(
                "[reauth] Temporary authentication error, "
                f"will check again later: {exc}",
                exc_info=exc,
            )
        else:
            # Successful authentication validation
            return True
        # Failed authentication validation
        return False

    async def _iterate_websockets(
        self, effective_read_timeout: float | None = None
    ):
        if not (access_token := self.access_token):
            raise MissingAccessTokenError

        # WebSockets session
        async with self._session.ws_connect(
            self.BASE_URL + f"/api/v4/updates/ws?access_token={access_token}",
            heartbeat=15.0,
        ) as ws:
            self.logger.debug("WebSockets connected")
            while not ws.closed:
                message = None
                if (
                    effective_read_timeout is not None
                    and effective_read_timeout > 0
                ):
                    async with timeout(effective_read_timeout):
                        while (
                            message is None
                            or message.type != aiohttp.WSMsgType.text
                        ):
                            if (message := await ws.receive()).type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.ERROR,
                                aiohttp.WSMsgType.CLOSE,
                            ):
                                break
                else:
                    message = await ws.receive()

                if message.type != aiohttp.WSMsgType.text:
                    break

                try:
                    contents = message.json()
                except json.JSONDecodeError:
                    self.logger.warning(f"Unknown message data: {message}")
                if isinstance(contents, Mapping):
                    self.logger.debug(f"Received WS message: {contents}")
                    yield contents
                else:
                    self.logger.warning(
                        "Received message is not "
                        f"a mapping (dict): {message}"
                    )

    async def async_listen_websockets(
        self,
        auto_restart: bool = False,
        auto_reauth: bool = True,
        effective_read_timeout: float | None = 180.0,
    ):
        while True:
            known_exception = None
            try:
                async for message in self._iterate_websockets(
                    effective_read_timeout
                ):
                    yield message
            except asyncio.CancelledError:
                self.logger.debug("WS listener stopped gracefully")
                raise

            # Handle temporary exceptions
            except TimeoutError as exc:
                known_exception = exc
                self.logger.error(f"WS temporary error: {exc}")

            except OSError as exc:
                known_exception = exc
                self.logger.error(f"WS OS Error: {exc}")

            except aiohttp.ClientError as exc:
                # @TODO: check if authentication is required
                known_exception = exc
                self.logger.error(f"WS client error: {exc}")

            except PandoraOnlineException as exc:
                known_exception = exc
                self.logger.error(f"WS API error: {exc}")

            else:
                self.logger.debug("WS client closed")

            # Raise exception
            if not auto_restart:
                raise (
                    known_exception
                    or PandoraOnlineException("WS closed prematurely")
                )

            # Reauthenticate if required
            while auto_reauth and not await self._do_ws_auto_auth():
                await asyncio.sleep(3.0)

            if not auto_reauth:
                # Sleep for all else
                await asyncio.sleep(3.0)

    async def async_listen_for_updates(
        self,
        *,
        state_callback: Callable[
            ["PandoraOnlineDevice", CurrentState, Mapping[str, Any]],
            Awaitable[None] | None,
        ]
        | None = None,
        command_callback: Callable[
            ["PandoraOnlineDevice", int, int, Any | None],
            Awaitable[None] | None,
        ]
        | None = None,
        event_callback: Callable[
            ["PandoraOnlineDevice", TrackingEvent],
            Awaitable[None] | None,
        ]
        | None = None,
        point_callback: Callable[
            [
                "PandoraOnlineDevice",
                TrackingPoint,
                CurrentState | None,
                Mapping[str, Any] | None,
            ],
            Awaitable[None] | None,
        ]
        | None = None,
        update_settings_callback: Callable[
            ["PandoraOnlineDevice", Mapping[str, Any]],
            Awaitable[None] | None,
        ]
        | None = None,
        reconnect_on_device_online: bool = True,
        auto_restart: bool = False,
        auto_reauth: bool = True,
        effective_read_timeout: float | None = 180.0,
    ) -> None:
        async def _handle_ws_message(
            contents: Mapping[str, Any]
        ) -> bool | None:
            """
            Handle WebSockets message.
            :returns: True = keep running, None = restart, False = stop
            """
            callback_coro = None

            # Extract message type and data
            try:
                type_, data = (
                    contents["type"],
                    contents["data"],
                )
            except LookupError:
                self.logger.error(f"WS malformed data: {contents}")
                return True

            # Extract device ID
            try:
                device_id = self.parse_device_id(data)
            except (TypeError, ValueError):
                self.logger.warning(
                    f"WS data with invalid device ID: {data['dev_id']}"
                )
                return True
            except LookupError:
                self.logger.warning(f"WS {type_} with no device ID: {data}")
                return True

            # Check presence of the device
            try:
                device = self._devices[device_id]
            except LookupError:
                self.logger.warning(
                    f"WS {type_} for unregistered "
                    f"device ID {device_id}: {data}"
                )
                return True

            return_result = True

            try:
                if type_ == WSMessageType.INITIAL_STATE:
                    result = self._process_ws_initial_state(device, data)
                    if state_callback:
                        callback_coro = state_callback(device, *result)

                elif type_ == WSMessageType.STATE:
                    prev_online = device.is_online
                    result = self._process_ws_state(device, data)
                    if (
                        reconnect_on_device_online
                        and not prev_online
                        and device.is_online
                    ):
                        self.logger.debug(
                            "Will restart WS to fetch new state "
                            f"after device {device_id} went online"
                        )
                        # Force reconnection to retrieve initial state immediately
                        return_result = None
                    if result is not None and state_callback:
                        callback_coro = state_callback(device, *result)

                elif type_ == WSMessageType.POINT:
                    result = self._process_ws_point(device, data)
                    if point_callback:
                        callback_coro = point_callback(device, *result)

                elif type_ == WSMessageType.COMMAND:
                    (
                        command_id,
                        result,
                        reply,
                    ) = self._process_ws_command(device, data)

                    if command_callback:
                        callback_coro = command_callback(
                            device,
                            command_id,
                            result,
                            reply,
                        )

                elif type_ == WSMessageType.EVENT:
                    result = self._process_ws_event(device, data)
                    if event_callback:
                        callback_coro = event_callback(device, result)

                elif type_ == WSMessageType.UPDATE_SETTINGS:
                    result = self._process_ws_update_settings(device, data)
                    if event_callback:
                        callback_coro = update_settings_callback(
                            device, result
                        )

                else:
                    self.logger.warning(
                        f"WS data of unknown type {type_}: {data}"
                    )
            except BaseException as exc:
                self.logger.warning(
                    "Error during preliminary response processing "
                    f"with message type {type_}: {repr(exc)}\nPlease, "
                    "report this error to the developer immediately!",
                    exc_info=exc,
                )
                return True

            if callback_coro is not None:
                try:
                    await asyncio.shield(callback_coro)
                except asyncio.CancelledError:
                    raise
                except BaseException as exc:
                    self.logger.exception(
                        f"Error during callback handling: {exc}"
                    )

            return return_result

        # On empty (none) responses, reconnect WS
        # On False response, stop WS
        response = None
        while response is not False:
            async for message in self.async_listen_websockets(
                auto_restart=auto_restart,
                auto_reauth=auto_reauth,
                effective_read_timeout=effective_read_timeout,
            ):
                if not (response := await _handle_ws_message(message)):
                    break

        self.logger.info("WS updates listener stopped")


class PandoraOnlineDevice:
    """Models state and remote services of one vehicle.

    :param account: ConnectedDrive account this vehicle belongs to
    :param attributes: attributes of the vehicle as provided by the server
    """

    def __init__(
        self,
        account: PandoraOnlineAccount,
        attributes: Mapping[str, Any],
        current_state: CurrentState | None = None,
        control_timeout: float = DEFAULT_CONTROL_TIMEOUT,
        utc_offset: int | None = None,
        *,
        logger: logging.Logger | logging.LoggerAdapter = _LOGGER,
    ) -> None:
        """
        Instantiate vehicle object.
        :param account:
        """
        self._account = account
        self._control_future: asyncio.Future | None = None
        self._features = None
        self._attributes = attributes
        self._current_state = current_state
        self._last_point: TrackingPoint | None = None
        self._last_event: TrackingEvent | None = None
        self._utc_offset = utc_offset

        # Control timeout setting
        self.control_timeout = control_timeout

        self.logger = logger

    def __repr__(self):
        return "<" + str(self) + ">"

    def __str__(self) -> str:
        """Use the name as identifier for the vehicle."""
        return (
            f"{self.__class__.__name__}["
            f"id={self.device_id}, "
            f'name="{self.name}", '
            f"account={self._account}, "
            f"features={self.features}"
            "]"
        )

    # State management
    @property
    def utc_offset(self) -> int:
        return (
            self.account.utc_offset
            if self._utc_offset is None
            else self._utc_offset
        )

    @utc_offset.setter
    def utc_offset(self, value: int | None) -> None:
        self._utc_offset = value

    @property
    def state(self) -> CurrentState | None:
        return self._current_state

    @state.setter
    def state(self, value: CurrentState) -> None:
        old_state = self._current_state

        if old_state is None:
            if self.control_busy:
                self._control_future.set_result(True)
                self._control_future = None
        else:
            if (
                self.control_busy
                and old_state.command_timestamp_utc
                < value.command_timestamp_utc
            ):
                self._control_future.set_result(True)
                self._control_future = None

        self._current_state = value

    @property
    def last_point(self) -> TrackingPoint | None:
        return self._last_point

    @last_point.setter
    def last_point(self, value: TrackingPoint | None) -> None:
        if value is None:
            self._last_point = None
            return

        if value.device_id != self.device_id:
            raise ValueError("Point does not belong to device identifier")

        timestamp = value.timestamp
        current_state = self._current_state
        if current_state is not None and (
            timestamp is None or current_state.state_timestamp < timestamp
        ):
            evolve_args = {}

            fuel = value.fuel
            if fuel is not None:
                evolve_args["fuel"] = fuel

            speed = value.speed
            if speed is not None:
                evolve_args["speed"] = speed

            evolve_args["latitude"] = value.latitude
            evolve_args["longitude"] = value.longitude

            self._current_state = attr.evolve(current_state, **evolve_args)

        self._last_point = value

    @property
    def last_event(self) -> TrackingEvent | None:
        return self._last_event

    @last_event.setter
    def last_event(self, value: TrackingEvent | None) -> None:
        self._last_event = value

    async def async_fetch_last_event(self) -> Optional[TrackingEvent]:
        try:
            return next(iter(await self.async_fetch_events(0, None, 1)))
        except StopIteration:
            return None

    async def async_fetch_events(
        self,
        timestamp_from: int = 0,
        timestamp_to: int | None = None,
        limit: int = 20,
    ) -> list[TrackingEvent]:
        return await self.account.async_fetch_events(
            timestamp_from, timestamp_to, limit
        )

    # Remote command execution section
    async def async_remote_command(
        self, command_id: int | CommandID, ensure_complete: bool = True
    ):
        """Proxy method to execute commands on corresponding vehicle object"""
        if self._current_state is None:
            raise PandoraOnlineException("state update is required")

        if self.control_busy:
            raise PandoraOnlineException("device is busy executing command")

        if ensure_complete:
            self._control_future = asyncio.Future()

        await self._account.async_remote_command(self.device_id, command_id)

        if ensure_complete:
            self.logger.debug(
                f"Ensuring command {command_id} completion "
                f"(timeout: {self.control_timeout})"
            )
            await asyncio.wait_for(self._control_future, self.control_timeout)
            self._control_future.result()

        self.logger.debug(f"Command {command_id} executed successfully")

    async def async_wake_up(self) -> None:
        return await self.account.async_wake_up_device(self.device_id)

    # Lock/unlock toggles
    async def async_remote_lock(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.LOCK, ensure_complete)

    async def async_remote_unlock(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.UNLOCK, ensure_complete
        )

    # Engine toggle
    async def async_remote_start_engine(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.START_ENGINE, ensure_complete
        )

    async def async_remote_stop_engine(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.STOP_ENGINE, ensure_complete
        )

    # Tracking toggle
    async def async_remote_enable_tracking(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.ENABLE_TRACKING, ensure_complete
        )

    async def async_remote_disable_tracking(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.DISABLE_TRACKING, ensure_complete
        )

    # Active security toggle
    async def async_enable_active_security(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.ENABLE_ACTIVE_SECURITY, ensure_complete
        )

    async def async_disable_active_security(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.DISABLE_ACTIVE_SECURITY, ensure_complete
        )

    # Coolant heater toggle
    async def async_remote_turn_on_coolant_heater(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.TURN_ON_BLOCK_HEATER, ensure_complete
        )

    async def async_remote_turn_off_coolant_heater(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.TURN_OFF_BLOCK_HEATER, ensure_complete
        )

    # External (timer_ channel toggle
    async def async_remote_turn_on_ext_channel(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.TURN_ON_EXT_CHANNEL, ensure_complete
        )

    async def async_remote_turn_off_ext_channel(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.TURN_OFF_EXT_CHANNEL, ensure_complete
        )

    # Service mode toggle
    async def async_remote_enable_service_mode(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.ENABLE_SERVICE_MODE, ensure_complete
        )

    async def async_remote_disable_service_mode(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.DISABLE_SERVICE_MODE, ensure_complete
        )

    # Various commands
    async def async_remote_trigger_horn(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TRIGGER_HORN, ensure_complete
        )

    async def async_remote_trigger_light(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TRIGGER_LIGHT, ensure_complete
        )

    async def async_remote_trigger_trunk(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TRIGGER_TRUNK, ensure_complete
        )

    @property
    def control_busy(self) -> bool:
        """Returns whether device is currently busy executing command."""
        return not (
            self._control_future is None or self._control_future.done()
        )

    def release_control_lock(self, error: Any | None = None) -> None:
        if self._control_future is None:
            raise ValueError("control lock is not in effect")

        if error is None:
            self._control_future.set_result(True)
            self._control_future = None

        else:
            self._control_future.set_exception(
                PandoraOnlineException(
                    f"Error while executing command: {error}",
                )
            )
            self._control_future = None

    # External property accessors
    @property
    def account(self) -> PandoraOnlineAccount:
        return self._account

    @property
    def device_id(self) -> int:
        return int(self._attributes["id"])

    @property
    def is_online(self) -> bool:
        """Returns whether vehicle can be deemed online"""
        current_state = self._current_state
        return current_state is not None and current_state.is_online

    # Attributes-related properties
    @property
    def attributes(self) -> Mapping[str, Any]:
        return MappingProxyType(self._attributes)

    @attributes.setter
    def attributes(self, value: Mapping[str, Any]):
        if int(value["id"]) != self.device_id:
            raise ValueError("device IDs must match")
        self._attributes = value
        self._features = None

    @property
    def features(self) -> Features | None:
        if self._features is None and isinstance(
            self._attributes.get("features"), Mapping
        ):
            self._features = Features.from_dict(self._attributes["features"])
        return self._features

    @property
    def type(self) -> str | None:
        return self._attributes.get("type")

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._attributes["name"]

    @property
    def model(self) -> str:
        """Get model of the device."""
        return self._attributes["model"]

    @property
    def firmware_version(self) -> str:
        return self._attributes["firmware"]

    @property
    def voice_version(self) -> str:
        return self._attributes["voice_version"]

    @property
    def color(self) -> str | None:
        return self._attributes.get("color")

    @property
    def car_type_id(self) -> int | None:
        return self._attributes.get("car_type")

    @property
    def car_type(self) -> str | None:
        car_type = self.car_type_id
        if car_type is None:
            return None
        if car_type == 1:
            return "truck"
        if car_type == 2:
            return "moto"
        return "car"

    @property
    def photo_id(self) -> str | None:
        return self._attributes.get("photo")

    @property
    def photo_url(self) -> str | None:
        photo_id = self.photo_id
        if not photo_id:
            return photo_id

        return f"/images/avatars/{photo_id}.jpg"

    @property
    def phone(self) -> str | None:
        return self._attributes.get("phone") or None

    @property
    def phone_other(self) -> str | None:
        return self._attributes.get("phone1") or None


class PandoraOnlineException(Exception):
    """Base class for Pandora Car Alarm System exceptions"""


class MalformedResponseError(PandoraOnlineException, ValueError):
    """Response does not match expected format."""


class AuthenticationError(PandoraOnlineException):
    """Authentication-related exception"""


class SessionExpiredError(AuthenticationError):
    """When access token deemed expired or not authenticated"""


class InvalidAccessTokenError(AuthenticationError):
    """When access token is deemed malformed."""


class MissingAccessTokenError(InvalidAccessTokenError):
    """When access token is missing on object"""
