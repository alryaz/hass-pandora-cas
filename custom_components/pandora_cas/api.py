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
    "CommandExecutionError",
    "MalformedResponseError",
    # Constants
    "DEFAULT_USER_AGENT",
    "DEFAULT_CONTROL_TIMEOUT",
]

import asyncio
import json
import logging
from contextlib import suppress
from enum import Flag, IntEnum, IntFlag, auto, StrEnum
from time import time
from types import MappingProxyType
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
    Dict,
    Final,
    Iterable,
    Mapping,
    Tuple,
    TypeVar,
    Union,
    List,
    SupportsFloat,
    SupportsInt,
    Optional,
)

import aiohttp
import attr

_LOGGER = logging.getLogger(__name__)

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
    ENABLE_SERVICE_MODE = 40
    DISABLE_SERVICE_MODE = 41

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


@attr.s(kw_only=True, frozen=True, slots=True)
class CurrentState:
    identifier: int = attr.ib()
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
    fuel_tanks: Collection[FuelTank] = attr.ib(default=None)

    state_timestamp: int | None = attr.ib(default=None)
    state_timestamp_utc: int | None = attr.ib(default=None)
    online_timestamp: int | None = attr.ib(default=None)
    online_timestamp_utc: int | None = attr.ib(default=None)
    settings_timestamp_utc: int | None = attr.ib(default=None)
    command_timestamp_utc: int | None = attr.ib(default=None)

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
            kwargs["bit_state"] = data["bit_state_1"]
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
    def get_ws_dict_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
        if "is_online" not in kwargs and "online_mode" in data:
            kwargs["is_online"] = bool(data["online_mode"])
        if "state_timestamp" not in kwargs and "state" in data:
            kwargs["state_timestamp"] = data["state"]
        if "state_timestamp_utc" not in kwargs and "state_utc" in data:
            kwargs["state_timestamp_utc"] = data["state_utc"]
        if "online_timestamp" not in kwargs and "online" in data:
            kwargs["online_timestamp"] = data["online"]
        if "online_timestamp_utc" not in kwargs and "online_utc" in data:
            kwargs["online_timestamp_utc"] = data["online_utc"]
        if "settings_timestamp_utc" not in kwargs and "setting_utc" in data:
            kwargs["settings_timestamp_utc"] = data["setting_utc"]
        if "command_timestamp_utc" not in kwargs and "command_utc" in data:
            kwargs["command_timestamp_utc"] = data["command_utc"]
        if "active_sim" not in kwargs and "active_sim" in data:
            kwargs["active_sim"] = data["active_sim"]
        if "tracking_remaining" not in kwargs and "track_remains" in data:
            kwargs["tracking_remaining"] = data["track_remains"]
        if "lock_latitude" not in kwargs and "lock_x" in data:
            if (lock_x := data["lock_x"]) is not None:
                lock_x = float(lock_x) / 1000000
            kwargs["lock_latitude"] = lock_x
        if "lock_longitude" not in kwargs and "lock_y" in data:
            if (lock_y := data["lock_y"]) is not None:
                lock_y = float(lock_y) / 1000000
            kwargs["lock_longitude"] = lock_y / 1000000
        if "can_average_speed" not in kwargs and "CAN_average_speed" in data:
            kwargs["can_average_speed"] = data["CAN_average_speed"]
        if (
            "can_tpms_front_left" not in kwargs
            and "CAN_TMPS_forvard_left" in data
        ):
            kwargs["can_tpms_front_left"] = data["CAN_TMPS_forvard_left"]
        if (
            "can_tpms_front_right" not in kwargs
            and "CAN_TMPS_forvard_right" in data
        ):
            kwargs["can_tpms_front_right"] = data["CAN_TMPS_forvard_right"]
        if "can_tpms_back_left" not in kwargs and "CAN_TMPS_back_left" in data:
            kwargs["can_tpms_back_left"] = data["CAN_TMPS_back_left"]
        if (
            "can_tpms_back_right" not in kwargs
            and "CAN_TMPS_back_right" in data
        ):
            kwargs["can_tpms_back_right"] = data["CAN_TMPS_back_right"]
        if "can_tpms_reserve" not in kwargs and "CAN_TMPS_reserve" in data:
            kwargs["can_tpms_reserve"] = data["CAN_TMPS_reserve"]
        if "can_glass_driver" not in kwargs and "CAN_driver_glass" in data:
            kwargs["can_glass_driver"] = data["CAN_driver_glass"]
        if (
            "can_glass_passenger" not in kwargs
            and "CAN_passenger_glass" in data
        ):
            kwargs["can_glass_passenger"] = data["CAN_passenger_glass"]
        if (
            "can_glass_back_left" not in kwargs
            and "CAN_back_left_glass" in data
        ):
            kwargs["can_glass_back_left"] = data["CAN_back_left_glass"]
        if (
            "can_glass_back_right" not in kwargs
            and "CAN_back_right_glass" in data
        ):
            kwargs["can_glass_back_right"] = data["CAN_back_right_glass"]
        if "can_belt_driver" not in kwargs and "CAN_driver_belt" in data:
            kwargs["can_belt_driver"] = data["CAN_driver_belt"]
        if "can_belt_passenger" not in kwargs and "CAN_passenger_belt" in data:
            kwargs["can_belt_passenger"] = data["CAN_passenger_belt"]
        if "can_belt_back_left" not in kwargs and "CAN_back_left_belt" in data:
            kwargs["can_belt_back_left"] = data["CAN_back_left_belt"]
        if (
            "can_belt_back_right" not in kwargs
            and "CAN_back_right_belt" in data
        ):
            kwargs["can_belt_back_right"] = data["CAN_back_right_belt"]
        if "can_low_liquid" not in kwargs and "CAN_low_liquid" in data:
            kwargs["can_low_liquid"] = data["CAN_low_liquid"]
        if "can_seat_taken" not in kwargs and "CAN_seat_taken" in data:
            kwargs["can_seat_taken"] = data["CAN_seat_taken"]
        if (
            "can_mileage_by_battery" not in kwargs
            and "CAN_mileage_by_battery" in data
        ):
            kwargs["can_mileage_by_battery"] = data["CAN_mileage_by_battery"]
        if (
            "can_mileage_to_empty" not in kwargs
            and "CAN_mileage_to_empty" in data
        ):
            kwargs["can_mileage_to_empty"] = data["CAN_mileage_to_empty"]
        if (
            "can_mileage_to_maintenance" not in kwargs
            and "CAN_mileage_to_maintenance" in data
        ):
            kwargs["can_mileage_to_maintenance"] = data[
                "CAN_mileage_to_maintenance"
            ]
        if (
            "ev_charging_connected" not in kwargs
            and "charging_connect" in data
        ):
            kwargs["ev_charging_connected"] = data["charging_connect"]
        if "ev_charging_slow" not in kwargs and "charging_slow" in data:
            kwargs["ev_charging_slow"] = data["charging_slow"]
        if "ev_charging_fast" not in kwargs and "charging_fast" in data:
            kwargs["ev_charging_fast"] = data["charging_fast"]
        if "ev_state_of_charge" not in kwargs and "SOC" in data:
            kwargs["ev_state_of_charge"] = data["SOC"]
        if "ev_state_of_health" not in kwargs and "SOH" in data:
            kwargs["ev_state_of_health"] = data["SOH"]
        if "ev_status_ready" not in kwargs and "ev_status_ready" in data:
            kwargs["ev_status_ready"] = data["ev_status_ready"]
        if (
            "battery_temperature" not in kwargs
            and "battery_temperature" in data
        ):
            kwargs["battery_temperature"] = data["battery_temperature"]
        # if "tanks" in data:
        #     kwargs["fuel_tanks"] = FuelTank.parse_fuel_tanks(data["tanks"])
        return cls.get_common_dict_args(data, **kwargs)

    @classmethod
    def get_http_dict_args(
        cls, data: Mapping[str, Any], **kwargs
    ) -> dict[str, Any]:
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
            kwargs["timestamp"] = data["dtime"]
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
        utc_offset: int | None = None,
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
    async def _handle_json_response(
        response: aiohttp.ClientResponse,
    ) -> Any:
        try:
            data = await response.json(content_type=None)
        except json.JSONDecodeError as e:
            # Raise for status first
            response.raise_for_status()

            # Seems to be an acceptable json response...
            raise MalformedResponseError("bad JSON encoding") from e

        if 400 <= response.status < 500:
            try:
                auth_error = (
                    data.get("error_text")
                    or data.get("status")
                    or "unknown auth error"
                )
            except AttributeError:
                auth_error = "malformed auth error"
            raise AuthenticationError(auth_error)

        # Raise for status at this point
        response.raise_for_status()

        # Return data ready for consumption
        return data

    @staticmethod
    async def _handle_dict_response(response: aiohttp.ClientResponse) -> dict:
        data = await PandoraOnlineAccount._handle_json_response(response)
        if not isinstance(data, dict):
            raise MalformedResponseError("response is not a mapping")
        return data

    @staticmethod
    async def _handle_list_response(response: aiohttp.ClientResponse) -> list:
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
                _LOGGER.error(
                    f"[{self}] Malformed access token checking "
                    f"response: {await response.text()}",
                    exc_info=e,
                )
                raise MalformedResponseError("Malformed checking response")

        _LOGGER.debug(
            f"[{self}] Received error response for "
            f"access token check: {response}"
        )

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
        _LOGGER.debug(f"[{self}] Authenticating access token: {access_token}")

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
            data = await self._handle_dict_response(response)

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

        _LOGGER.info(f"[{self}] Access token authentication successful")

    async def async_authenticate(
        self, access_token: str | None = None
    ) -> None:
        if access_token:
            try:
                await self.async_apply_access_token(access_token)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.warning(
                    f"[{self}] Authentication with "
                    f"provided access token failed: {exc}",
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
                _LOGGER.warning(
                    f"[{self}] Authentication with "
                    f"existing access token failed: {exc}",
                    exc_info=exc,
                )
            else:
                return

        try:
            access_token = await self.async_fetch_access_token()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.error(
                f"[{self}] Could not retrieve access token: {exc}",
                exc_info=exc,
            )
            raise

        try:
            await self.async_apply_access_token(access_token)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            _LOGGER.error(
                f"[{self}] Authentication with fetched "
                f"access token failed: {exc}",
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

        _LOGGER.debug(f"[{self}] Retrieving devices")

        async with self._session.get(
            self.BASE_URL + "/api/devices",
            params={"access_token": access_token},
            raise_for_status=True,
        ) as response:
            devices_data = await self._handle_list_response(response)

        _LOGGER.debug(f"[{self}] Retrieved devices: {devices_data}")

        for device_attributes in devices_data:
            try:
                device_id = self.parse_device_id(device_attributes)
            except (TypeError, ValueError, LookupError) as exc:
                _LOGGER.error(
                    f"[{self}] Error parsing device ID: {exc}", exc_info=exc
                )
            else:
                try:
                    device_object = self._devices[device_id]
                except LookupError:
                    _LOGGER.debug(
                        f"[{self}] Adding new device with ID {device_id}"
                    )
                    self._devices[device_id] = PandoraOnlineDevice(
                        self, device_attributes
                    )
                else:
                    device_object.attributes = device_attributes

    async def async_remote_command(
        self, device_id: int, command_id: Union[int, "CommandID"]
    ) -> None:
        _LOGGER.debug(
            f"[{self}] Sending command {command_id} to device {device_id}"
        )

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
                _LOGGER.error(
                    f"[{self}] Error sending command {command_id} "
                    f"to device {device_id}: {status}"
                )
                raise CommandExecutionError(status)

            response.raise_for_status()

        _LOGGER.debug(
            f"[{self}] Command {command_id} sent to device {device_id}"
        )

    async def async_wake_up_device(self, device_id: int) -> None:
        _LOGGER.debug(f"[{self}] Waking up device {device_id}")

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
                _LOGGER.error(
                    f"[{self}] Error waking up device {device_id}: {status}"
                )
                raise CommandExecutionError(status)

            response.raise_for_status()

        _LOGGER.debug(f"[{self}] Sent wake up command to device {device_id}")

    async def async_fetch_device_settings(
        self, device_id: int | str
    ) -> dict[str, Any]:
        async with self._session.get(
            self.BASE_URL + "/api/devices/settings",
            params={"access_token": self.access_token, "id": device_id},
        ) as response:
            data = await self._handle_dict_response(response)

        try:
            devices_settings = data["device_settings"]
        except KeyError as exc:
            raise MalformedResponseError(
                "device_settings not present in response"
            ) from exc

        if not (device_id is None or device_id in devices_settings):
            raise MalformedResponseError(
                "settings for requested device not present in response"
            )

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
    ) -> Tuple[FuelTank, ...]:
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

    @staticmethod
    def _update_device_current_state(
        device: "PandoraOnlineDevice", **state_args
    ) -> Tuple[CurrentState, dict[str, Any]]:
        # Extract UTC offset
        if (utc_offset := device._utc_offset) is None:
            for prefix in ("online", "state"):
                utc = (non_utc := prefix + "_timestamp") + "_utc"
                if utc in state_args and non_utc in state_args:
                    device._utc_offset = utc_offset = (
                        round((state_args[non_utc] - state_args[utc]) / 60)
                        * 60
                    )
                    break

        # Adjust for two timestamps
        for prefix in ("online", "state"):
            utc = (non_utc := prefix + "_timestamp") + "_utc"
            if utc in state_args:
                if non_utc not in state_args:
                    state_args[non_utc] = state_args[utc] + utc_offset
            elif non_utc in state_args:
                state_args[utc] = state_args[non_utc] - utc_offset

        # Create new state or evolve existing
        if (state := device.state) is None:
            device.state = state = CurrentState(**state_args)
        else:
            device.state = attr.evolve(state, **state_args)

        # noinspection PyTypeChecker
        return state, state_args

    def _process_http_event(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> TrackingEvent:
        event = TrackingEvent.from_dict(data, device_id=device.device_id)

        if (e := device.last_event) and e.timestamp < event.timestamp:
            device.last_event = TrackingEvent

        return event

    def _process_http_stats(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[CurrentState, dict[str, Any]]:
        return self._update_device_current_state(
            device,
            **CurrentState.get_common_dict_args(
                data,
                identifier=device.device_id,
            ),
            is_online=bool(data.get("online")),
        )

    def _process_http_times(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[CurrentState, dict[str, Any]]:
        # @TODO: unknown timestamp format

        return self._update_device_current_state(
            device,
            online_timestamp=data.get("onlined"),
            online_timestamp_utc=data.get("online"),
            command_timestamp_utc=data.get("command"),
            settings_timestamp_utc=data.get("setting"),
        )

    async def async_request_updates(
        self, timestamp: int | None = None
    ) -> Tuple[dict[int, Dict[str, Any]], List[TrackingEvent]]:
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

        _LOGGER.debug(f"[{self}] Fetching changes since {_timestamp}")

        async with self._session.get(
            self.BASE_URL + "/api/updates",
            params={"ts": _timestamp, "access_token": access_token},
            raise_for_status=True,
        ) as response:
            data = await self._handle_dict_response(response)

        device_new_attrs: dict[int, Dict[str, Any]] = {}

        # Stats / time updates
        for key, meth in (
            ("stats", self._process_http_stats),
            ("time", self._process_http_times),
        ):
            # Check if response contains necessary data
            if not (mapping := data.get(key)):
                continue

            # Iterate over device responses
            for device_id, device_data in mapping.items():
                try:
                    device = self._devices[int(device_id)]
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        f"[{self}] Bad device ID in {key} data: {device_id}"
                    )
                except LookupError:
                    _LOGGER.warning(
                        f"[{self}] Received {key} data for "
                        f"uninitialized device {device_id}: {device_data}"
                    )
                    continue
                else:
                    # Process attributes and merge into final dict
                    _, new_attrs = meth(device, device_data)
                    try:
                        device_new_attrs[device.device_id].update(new_attrs)
                    except KeyError:
                        device_new_attrs[device.device_id] = new_attrs

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
                _LOGGER.warning(
                    f"[{self}] Bad device ID in event data: {raw_device_id}"
                )
                continue
            except LookupError:
                _LOGGER.warning(
                    f"[{self}] Received event data for "
                    f"uninitialized device {raw_device_id}: {event_obj}"
                )
                continue

            events.append(self._process_ws_event(device, event_obj))

        if device_new_attrs:
            _LOGGER.debug(
                f"[{self}] Received updates from HTTP: {device_new_attrs}"
            )

        try:
            self._last_update = int(data["ts"])
        except (LookupError, TypeError, ValueError):
            _LOGGER.warning(f"[{self}] Response did not contain timestamp")

        return device_new_attrs, events

    def _process_ws_initial_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[CurrentState, dict[str, Any]]:
        _LOGGER.debug(
            f"[{self}] Initializing state for {device.device_id} from {data}"
        )

        return self._update_device_current_state(
            device,
            **CurrentState.get_ws_dict_args(
                data, identifier=device.device_id
            ),
        )

    def _process_ws_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[CurrentState, dict[str, Any | None]]:
        device_state = device.state
        # if device_state is None:
        #     _LOGGER.warning(
        #         f"Device with ID '{device.device_id}' partial state data retrieved, "
        #         f"but no initial data has yet been received. Skipping...",
        #     )
        #
        #     return None

        _LOGGER.debug(f"[{self}] Updating state for {device.device_id}")

        return self._update_device_current_state(
            device,
            **CurrentState.get_ws_dict_args(
                data, identifier=device.device_id
            )
        )

    # The routines are virtually the same
    _process_ws_event = _process_http_event

    def _process_ws_point(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> TrackingPoint:
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

        return TrackingPoint(
            device_id=device.device_id,
            track_id=data["track_id"],
            latitude=data["x"],
            longitude=data["y"],
            timestamp=data.get("dtime") or time(),
            fuel=fuel,
            speed=speed,
            max_speed=max_speed,
            length=length,
        )

    def _process_ws_command(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[int, int, int]:
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

    def _process_ws_update_settings(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # @TODO: do something?
        return {
            "device_id": device.device_id,
        }

    async def async_listen_websockets(self, auto_restart: bool = False):
        if not (access_token := self.access_token):
            raise MissingAccessTokenError

        while True:
            known_exception = None
            try:
                # WebSockets session
                async with self._session.ws_connect(
                    self.BASE_URL
                    + f"/api/v4/updates/ws?access_token={access_token}",
                    heartbeat=15.0,
                ) as ws:
                    _LOGGER.debug(f"[{self}] WebSockets connected")
                    while not ws.closed:
                        message = await ws.receive()
                        if message.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.ERROR,
                            aiohttp.WSMsgType.CLOSE,
                        ):
                            break
                        if message.type == aiohttp.WSMsgType.text:
                            try:
                                contents = message.json()
                            except json.JSONDecodeError:
                                _LOGGER.warning(
                                    f"[{self}] Unknown message data: {message}"
                                )
                            if isinstance(contents, Mapping):
                                _LOGGER.debug(f'[{self}] Received WS message: {contents}')
                                yield contents
                            else:
                                _LOGGER.warning(
                                    f"[{self}] Received message is not "
                                    f"a mapping (dict): {message}"
                                )

            except TimeoutError as exc:
                known_exception = exc
                _LOGGER.error(
                    f"[{self}] Timed out (WS might have failed)", exc_info=exc
                )

            except OSError as exc:
                known_exception = exc
                _LOGGER.error(f"[{self}] OS Error: {exc}", exc_info=exc)

            except aiohttp.ClientError as exc:
                known_exception = exc
                _LOGGER.error(f"[{self}] Client error: {exc}", exc_info=exc)

            except asyncio.CancelledError:
                _LOGGER.debug(f"[{self}] WS listener stopped")
                raise

            else:
                _LOGGER.debug(f"[{self}] WS client closed")

            if not auto_restart:
                raise (
                    known_exception
                    or PandoraOnlineException("WS closed prematurely")
                )

            # Reauthenticate if required
            try:
                _LOGGER.debug(
                    f"[{self}] Checking WS access token before reauth"
                )
                await self.async_check_access_token(access_token)
            except AuthenticationError:
                _LOGGER.debug(f"[{self}] Performing WS reauth")
                await self.async_authenticate(access_token)
            else:
                _LOGGER.debug(f"[{self}] WS access token still valid")

            # Sleep just in case
            await asyncio.sleep(3.0)

    async def async_listen_for_updates(
        self,
        *,
        state_callback: Callable[
            ["PandoraOnlineDevice", CurrentState, Mapping[str, Any]],
            Union[Awaitable[None], None],
        ]
        | None = None,
        command_callback: Callable[
            ["PandoraOnlineDevice", int, int, Any | None],
            Union[Awaitable[None], None],
        ]
        | None = None,
        event_callback: Callable[
            ["PandoraOnlineDevice", TrackingEvent | None],
            Union[Awaitable[None], None],
        ]
        | None = None,
        point_callback: Callable[
            ["PandoraOnlineDevice", TrackingPoint | None],
            Union[Awaitable[None], None],
        ]
        | None = None,
        update_settings_callback: Callable[
            ["PandoraOnlineDevice", Mapping[str, Any | None]],
            Union[Awaitable[None], None],
        ]
        | None = None,
        reconnect_on_device_online: bool = True,
        **kwargs,
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
                _LOGGER.error(f"[{self}] WS malformed data: {contents}")
                return True

            # Extract device ID
            try:
                device_id = self.parse_device_id(data)
            except (TypeError, ValueError):
                _LOGGER.warning(
                    f"[{self}] WS data with invalid "
                    f"device ID: {data['dev_id']}"
                )
                return True
            except LookupError:
                _LOGGER.warning(
                    f"[{self}] WS {type_} with no " f"device ID: {data}"
                )
                return True

            # Check presence of the device
            try:
                device = self._devices[device_id]
            except LookupError:
                _LOGGER.warning(
                    f"[{self}] WS {type_} for unregistered "
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
                        _LOGGER.debug(
                            f"[{self}] Will restart WS to fetch new state "
                            f"after device {device_id} went online"
                        )
                        # Force reconnection to retrieve initial state immediately
                        return_result = None
                    if result is not None and state_callback:
                        callback_coro = state_callback(device, *result)

                elif type_ == WSMessageType.POINT:
                    result = self._process_ws_point(device, data)
                    if point_callback:
                        callback_coro = point_callback(device, result)

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
                    _LOGGER.warning(
                        f"[{self}] WS data of unknown " f"type {type_}: {data}"
                    )
            except BaseException as exc:
                _LOGGER.warning(
                    f"Error during preliminary response processing "
                    f"with message type {type_}: {repr(exc)}\nPlease, "
                    f"report this error to the developer immediately!",
                    exc_info=exc,
                )
                return True

            if callback_coro is not None:
                try:
                    await asyncio.shield(callback_coro)
                except asyncio.CancelledError:
                    raise
                except BaseException as exc:
                    _LOGGER.exception(
                        f"[{self}] Error during " f"callback handling: {exc}"
                    )

            return return_result

        with suppress(asyncio.CancelledError):
            response = None

            # On empty (none) responses, reconnect WS
            while response is not False:
                async for message in self.async_listen_websockets(**kwargs):
                    if not (response := await _handle_ws_message(message)):
                        break


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
    ) -> None:
        """
        Instantiate vehicle object.
        :param account:
        """
        if not (utc_offset is None or (-86400 < utc_offset < 86400)):
            raise ValueError("utc offset cannot be greater than 24 hours")

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
            f"]"
        )

    # State management
    @property
    def utc_offset(self) -> int:
        return (
            self.account.utc_offset
            if self._utc_offset is None
            else self._utc_offset
        )

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

    # Remote command execution section
    async def async_remote_command(
        self, command_id: Union[int, CommandID], ensure_complete: bool = True
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
            try:
                _LOGGER.debug(
                    "Ensuring command completion (timeout: %d seconds)"
                    % (self.control_timeout,)
                )
                await asyncio.wait_for(
                    self._control_future, self.control_timeout
                )
                self._control_future.result()

            except asyncio.TimeoutError:
                raise CommandExecutionError("timeout executing command")

        _LOGGER.debug("Command executed successfully")

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


class CommandExecutionError(PandoraOnlineException):
    pass
