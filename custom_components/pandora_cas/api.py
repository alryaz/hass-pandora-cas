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
    # Exceptions
    "PandoraOnlineException",
    "AuthenticationException",
    "RequestException",
    "CommandExecutionException",
    # Constants
    "DEFAULT_USER_AGENT",
    "DEFAULT_CONTROL_TIMEOUT",
]

import asyncio
import json
import logging
from enum import Flag, IntEnum, IntFlag, auto
from json import JSONDecodeError
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
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import aiohttp
import async_timeout
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
    TURN_ON_COOLANT_HEATER = 21
    TURN_OFF_COOLANT_HEATER = 22

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
    TRIGGER_TRUNK = 34
    CHECK = 255

    ERASE_DTC = 57856
    READ_DTC = 57857

    # Additional commands
    ADDITIONAL_COMMAND_1 = 100
    ADDITIONAL_COMMAND_2 = 128

    # Connection toggle
    ENABLE_CONNECTION = 240
    DISABLE_CONNECTION = 15


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
    HANDS_FREE_LOCKED = pow(2, 5)
    HANDS_FREE_UNLOCKED = pow(2, 6)
    GSM_ACTIVE = pow(2, 7)
    GPS_ACTIVE = pow(2, 8)
    TRACKING_ENABLED = pow(2, 9)
    IMMOBILIZER_ENABLED = pow(2, 10)
    EXT_SENSOR_ALERT_ZONE = pow(2, 11)
    EXT_SENSOR_MAIN_ZONE = pow(2, 12)
    SENSOR_ALERT_ZONE = pow(2, 13)
    SENSOR_MAIN_ZONE = pow(2, 14)
    AUTOSTART_ENABLED = pow(2, 15)  # AutoStart function is available
    INCOMING_SMS_ENABLED = pow(2, 16)  # Incoming SMS messages are allowed
    INCOMING_CALLS_ENABLED = pow(2, 17)  # Incoming calls are allowed
    EXTERIOR_LIGHTS_ACTIVE = pow(2, 18)  # Any exterior lights are active
    SIREN_WARNINGS_ENABLED = pow(2, 19)  # Siren warning signals disabled
    SIREN_SOUND_ENABLED = pow(2, 20)  # All siren signals disabled
    DOOR_FRONT_LEFT_OPEN = pow(2, 21)  # Door open: front left
    DOOR_FRONT_RIGHT_OPEN = pow(2, 22)  # Door open: front right
    DOOR_BACK_LEFT_OPEN = pow(2, 23)  # Door open: back left
    DOOR_BACK_RIGHT_OPEN = pow(2, 24)  # Door open: back right
    TRUNK_OPEN = pow(2, 25)  # Trunk open
    HOOD_OPEN = pow(2, 26)  # Hood open
    HANDBRAKE_ENGAGED = pow(2, 27)  # Handbrake is engaged
    BRAKES_ENGAGED = pow(2, 28)  # Pedal brake is engaged
    BLOCK_HEATER_ACTIVE = pow(2, 29)  # Pre-start heater active
    ACTIVE_SECURITY = pow(2, 30)  # Active security active
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
    COOLANT_HEATER = auto()
    KEEP_ALIVE = auto()
    LIGHT_TOGGLE = auto()
    NOTIFICATIONS = auto()
    SCHEDULE = auto()
    SENSORS = auto()
    TRACKING = auto()
    TRUNK_TRIGGER = auto()

    @classmethod
    def from_dict(
        cls, features_dict: Dict[str, Union[bool, int]]
    ) -> Optional["Features"]:
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
            "heater": cls.COOLANT_HEATER,
            "keep_alive": cls.KEEP_ALIVE,
            "light": cls.LIGHT_TOGGLE,
            "notification": cls.NOTIFICATIONS,
            "schedule": cls.SCHEDULE,
            "sensors": cls.SENSORS,
            "tracking": cls.TRACKING,
            "trunk": cls.TRUNK_TRIGGER,
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


@attr.s(kw_only=True, frozen=True, slots=True)
class FuelTank:
    id: int = attr.ib()
    value: float = attr.ib()
    ras: Optional[float] = attr.ib(default=None)
    ras_t: Optional[float] = attr.ib(default=None)

    def __float__(self) -> float:
        return self.value

    def __int__(self) -> int:
        return int(self.value)

    def __round__(self, n=None):
        return round(self.value, n)


_T = TypeVar("_T")


def _empty_is_none(x: _T) -> Optional[_T]:
    return x or None


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
    latitude: float = attr.ib()
    longitude: float = attr.ib()
    speed: float = attr.ib()
    bit_state: BitStatus = attr.ib()
    engine_rpm: int = attr.ib()
    engine_temperature: float = attr.ib(converter=float)
    interior_temperature: float = attr.ib(converter=float)
    exterior_temperature: float = attr.ib(converter=float)
    fuel: float = attr.ib(converter=float)
    voltage: float = attr.ib(converter=float)
    gsm_level: int = attr.ib()
    balance: Optional[BalanceState] = attr.ib(default=None)
    mileage: float = attr.ib(converter=float)
    can_mileage: float = attr.ib(converter=float)
    tag_number: int = attr.ib()
    key_number: int = attr.ib()
    relay: int = attr.ib()
    is_moving: bool = attr.ib(converter=bool)
    is_evacuating: bool = attr.ib(converter=bool)
    lock_latitude: float = attr.ib(converter=float)
    lock_longitude: float = attr.ib(converter=float)
    rotation: float = attr.ib(converter=float)
    phone: Optional[str] = attr.ib(default=None, converter=_empty_is_none)
    imei: Optional[int] = attr.ib(default=None, converter=_empty_is_none)
    phone_other: Optional[str] = attr.ib(
        default=None, converter=_empty_is_none
    )
    active_sim: int = attr.ib()
    tracking_remaining: Optional[float] = attr.ib(
        default=None, converter=_empty_is_none
    )

    can_tpms_front_left: Optional[float] = attr.ib(default=None)
    can_tpms_front_right: Optional[float] = attr.ib(default=None)
    can_tpms_back_left: Optional[float] = attr.ib(default=None)
    can_tpms_back_right: Optional[float] = attr.ib(default=None)
    can_glass_front_left: Optional[bool] = attr.ib(default=None)
    can_glass_front_right: Optional[bool] = attr.ib(default=None)
    can_glass_back_left: Optional[bool] = attr.ib(default=None)
    can_glass_back_right: Optional[bool] = attr.ib(default=None)
    can_low_liquid_warning: Optional[bool] = attr.ib(default=None)
    can_mileage_by_battery: Optional[float] = attr.ib(default=None)
    can_mileage_until_empty: Optional[float] = attr.ib(default=None)

    ev_charging_connected: Optional[bool] = attr.ib(default=None)
    ev_charging_slow: Optional[bool] = attr.ib(default=None)
    ev_charging_fast: Optional[bool] = attr.ib(default=None)
    ev_status_ready: Optional[bool] = attr.ib(default=None)
    battery_temperature: Optional[int] = attr.ib(default=None)

    # undecoded parameters
    smeter: int = attr.ib(default=None)
    tconsum: int = attr.ib(default=None)
    loadaxis: Any = attr.ib(default=None)
    land: int = attr.ib(default=None)
    bunker: int = attr.ib(default=None)
    ex_status: int = attr.ib(default=None)
    balance_other: Any = attr.ib(default=None)
    fuel_tanks: Collection[FuelTank] = attr.ib(default=None)

    state_timestamp: int = attr.ib()
    state_timestamp_utc: int = attr.ib()
    online_timestamp: int = attr.ib()
    online_timestamp_utc: int = attr.ib()
    settings_timestamp_utc: int = attr.ib()
    command_timestamp_utc: int = attr.ib()

    @property
    def direction(self) -> str:
        """Textual interpretation of rotation."""
        return _degrees_to_direction(self.rotation)


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


@attr.s(kw_only=True, frozen=True, slots=True)
class TrackingPoint:
    identifier: int = attr.ib()
    latitude: float = attr.ib()
    longitude: float = attr.ib()
    track_id: Optional[int] = attr.ib(default=None)
    timestamp: float = attr.ib(default=time)
    fuel: Optional[int] = attr.ib(default=None)
    speed: Optional[float] = attr.ib(default=None)
    max_speed: Optional[float] = attr.ib(default=None)
    length: Optional[float] = attr.ib(default=None)


class PandoraOnlineAccount:
    """Pandora Online account interface."""

    BASE_URL = "https://pro.p-on.ru"

    def __init__(
        self,
        username: str,
        password: str,
        access_token: Optional[str] = None,
    ) -> None:
        """
        Instantiate Pandora Online account object.
        :param username: Account username
        :param password: Account password
        :param access_token: Access token (optional)
        """
        self._username = username
        self._password = password
        self._access_token = access_token
        self._session = aiohttp.ClientSession()

        #: last update timestamp
        self._last_update = -1

        #: properties generated upon authentication
        self._session_id = None
        self._user_id = None

        #: list of vehicles associated with this account.
        self._devices: List[PandoraOnlineDevice] = list()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._session.__aexit__(exc_type, exc_val, exc_tb)

    async def async_close(self):
        await self._session.close()

    def __repr__(self):
        """Retrieve representation of account object"""
        return "<" + str(self) + ">"

    def __str__(self):
        return '%s[username="%s"]' % (self.__class__.__name__, self._username)

    # Basic properties
    @property
    def username(self) -> str:
        """Username accessor."""
        return self._username

    @property
    def last_update(self) -> int:
        return self._last_update

    @property
    def devices(self) -> Tuple["PandoraOnlineDevice"]:
        """Devices (immutable) accessor."""
        return tuple(self._devices)

    def get_device(
        self, device_id: Union[int, str]
    ) -> Optional["PandoraOnlineDevice"]:
        _device_id = int(device_id)
        for device in self._devices:
            if _device_id == device.device_id:
                return device

    # Remote action handlers
    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        expected_status: int = 200,
        check_status_field: Union[bool, str] = False,
    ):
        try:
            if response.status != expected_status:
                raise RequestException(
                    f"unexpected status", response.status
                ) from None

            content = await response.json()

            if check_status_field and content.get("status") == (
                "success" if check_status_field is True else check_status_field
            ):
                raise RequestException("invalid response", content) from None

            return content

        except JSONDecodeError:
            raise RequestException(
                "unknown server response format", await response.text()
            ) from None

        except aiohttp.ClientConnectionError:
            raise RequestException("connection error") from None

        except aiohttp.ClientResponseError:
            raise RequestException("invalid server response") from None

        except aiohttp.ClientError as e:
            raise RequestException("HTTP client error: %s" % (e,)) from None

    # Requests
    async def async_fetch_access_token(self) -> str:
        async with self._session.post(
            self.BASE_URL + "/oauth/token",
            headers={
                "Authorization": "Basic cGNvbm5lY3Q6SW5mXzRlUm05X2ZfaEhnVl9zNg==",
            },
        ) as response:
            if response.status != 200:
                raise PandoraOnlineException(
                    f"Unexpected response code while fetching access token: {response.status}"
                )
            try:
                return (await response.json())["access_token"]
            except json.JSONDecodeError:
                raise PandoraOnlineException("Could not decode access token")
            except KeyError:
                raise PandoraOnlineException("Access token not found")
            except aiohttp.ClientError as e:
                raise PandoraOnlineException(
                    f"Error fetching access token: {e}"
                )
            except asyncio.TimeoutError:
                raise PandoraOnlineException("Timeout fetching access token")

    async def async_authenticate(self, access_token: Optional[str] = None):
        _LOGGER.debug('Authenticating with username "%s"' % (self._username,))

        self._session.cookie_jar.clear()

        if access_token is None:
            access_token = await self.async_fetch_access_token()

        url = self.BASE_URL + "/api/users/login"
        request_data = {
            "login": self._username,
            "password": self._password,
            "lang": "ru",
            "v": "3",
            "utc_offset": 180,
            "access_token": access_token,
        }

        async with self._session.post(url, data=request_data) as response:
            try:
                await self._handle_response(response)
            except RequestException as e:
                raise AuthenticationException(*e.args) from None

            _LOGGER.info(
                'Authentication successful for username "%s"!'
                % (self._username,)
            )
            self._access_token = access_token

    async def async_update_vehicles(self):
        """Retrieve and cache list of vehicles for the account."""
        access_token = self._access_token
        if access_token is None:
            raise PandoraOnlineException("Account is not authenticated")

        _LOGGER.debug(
            'Updating vehicle list for username "%s"' % (self._username,)
        )

        async with self._session.get(
            self.BASE_URL + "/api/devices",
            params={"access_token": self._access_token},
        ) as response:
            devices_data = await self._handle_response(response)
            _LOGGER.debug("retrieved devices: %s", devices_data)

        new_devices_list = []

        for device_attributes in devices_data:
            device_id = int(device_attributes["id"])
            device_object = self.get_device(device_id)

            if device_object is None:
                device_object = PandoraOnlineDevice(self, device_attributes)
                _LOGGER.debug(f"Found new device: {device_object}")
            else:
                device_object.attributes = device_attributes

            new_devices_list.append(device_object)

        self._devices = new_devices_list

    async def async_remote_command(
        self, device_id: int, command_id: Union[int, "CommandID"]
    ):
        access_token = self._access_token
        if access_token is None:
            raise PandoraOnlineException("Account is not authenticated")

        _LOGGER.debug(
            'Sending command "%d" to device "%d"' % (command_id, device_id)
        )

        async with self._session.post(
            self.BASE_URL + "/api/devices/command",
            data={"id": device_id, "command": int(command_id)},
            params={"access_token": self._access_token},
        ) as response:
            command_result = await self._handle_response(response)
            status = command_result.get("action_result", {}).get(
                str(device_id)
            )

            if status != "sent":
                raise CommandExecutionException(
                    "could not execute command", status
                )

            _LOGGER.debug(
                'Command "%d" sent to device "%d"' % (command_id, device_id)
            )

    async def async_fetch_changes(self, timestamp: Optional[int] = None):
        """
        Fetch latest changes from update server.
        :param timestamp:
        :return: (New data, Set of updated device IDs)
        """
        access_token = self._access_token
        if access_token is None:
            raise PandoraOnlineException("Account is not authenticated")

        _timestamp = self._last_update if timestamp is None else timestamp

        _LOGGER.debug(f"Fetching changes since {_timestamp} on account {self}")

        async with self._session.get(
            self.BASE_URL + "/api/updates",
            params={"ts": _timestamp, "access_token": access_token},
        ) as response:
            content: Dict[str, Any] = await self._handle_response(response)

        updated_device_ids = set()

        # Time updates
        if content.get("time"):
            for device_id, times_data in content["time"].items():
                device_object = self.get_device(device_id)
                if device_object:
                    _LOGGER.debug(
                        "Updating times data for device %s" % (device_object,)
                    )
                    device_object.times = times_data
                    updated_device_ids.add(device_object.device_id)
                else:
                    _LOGGER.warning(
                        'Device with ID "%s" times data retrieved, '
                        "but no object created yet. Skipping..."
                    )

        # Stats updates
        if content.get("stats"):
            for device_id, stats_data in content["stats"].items():
                device_object = self.get_device(device_id)
                if device_object:
                    _LOGGER.debug(
                        "Updating stats data for device %s" % (device_object,)
                    )
                    device_object.state = stats_data
                    updated_device_ids.add(device_object.device_id)

                else:
                    _LOGGER.warning(
                        'Device with ID "%s" stats data retrieved, '
                        "but no object created yet. Skipping..." % (device_id,)
                    )

        self._last_update = int(content["ts"])

        return content, updated_device_ids

    def _process_ws_initial_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Tuple[CurrentState, Dict[str, Any]]:
        _LOGGER.debug(
            f"Initializing stats data for device with ID '{device.device_id}'"
        )

        current_state_args = dict(
            identifier=data["id"],
            latitude=data["x"],
            longitude=data["y"],
            speed=data["speed"],
            bit_state=BitStatus(int(data["bit_state_1"])),
            engine_rpm=data["engine_rpm"],
            engine_temperature=data["engine_temp"],
            interior_temperature=data["cabin_temp"],
            exterior_temperature=data["out_temp"],
            balance=(
                BalanceState(
                    value=data["balance"]["value"],
                    currency=data["balance"]["cur"],
                )
                if data["balance"]
                else None
            ),
            balance_other=(
                BalanceState(
                    value=data["balance1"]["value"],
                    currency=data["balance1"]["cur"],
                )
                if data["balance1"]
                else None
            ),
            mileage=data["mileage"],
            can_mileage=data["mileage_CAN"],
            tag_number=data["metka"],
            key_number=data["brelok"],
            is_moving=data["move"],
            is_evacuating=data["evaq"],
            fuel=data["fuel"],
            gsm_level=data["gsm_level"],
            relay=data["relay"],
            voltage=data["voltage"],
            state_timestamp=data["state"],
            state_timestamp_utc=data["state_utc"],
            online_timestamp=data["online"],
            online_timestamp_utc=data["online_utc"],
            settings_timestamp_utc=data["setting_utc"],
            command_timestamp_utc=data["command_utc"],
            active_sim=data["active_sim"],
            tracking_remaining=data["track_remains"],
            lock_latitude=data["lock_x"] / 1000000,
            lock_longitude=data["lock_y"] / 1000000,
            rotation=data["rot"],
            can_tpms_front_left=data.get("CAN_TMPS_forvard_left"),
            can_tpms_front_right=data.get("CAN_TMPS_forvard_right"),
            can_tpms_back_left=data.get("CAN_TMPS_back_left"),
            can_tpms_back_right=data.get("CAN_TMPS_back_right"),
            can_glass_front_left=data.get("CAN_driver_glass"),
            can_glass_front_right=data.get("CAN_passenger_glass"),
            can_glass_back_left=data.get("CAN_back_left_glass"),
            can_glass_back_right=data.get("CAN_back_right_glass"),
            can_low_liquid_warning=data.get("CAN_low_liquid"),
            can_mileage_by_battery=data.get("CAN_mileage_by_battery"),
            can_mileage_until_empty=data.get("CAN_mileage_to_empty"),
            ev_charging_connected=data.get("charging_connect"),
            ev_charging_slow=data.get("charging_slow"),
            ev_charging_fast=data.get("charging_fast"),
            ev_status_ready=data.get("ev_status_ready"),
            battery_temperature=data.get("battery_temperature"),
            fuel_tanks=self.parse_fuel_tanks(data.get("tanks")),
        )

        current_state = CurrentState(**current_state_args)
        device.state = current_state

        return current_state, current_state_args

    @staticmethod
    def parse_fuel_tanks(
        fuel_tanks_data: Optional[Iterable[Mapping[str, Any]]],
        existing_fuel_tanks: Optional[Collection[FuelTank]] = None,
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

    def _process_ws_state(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> Optional[Tuple[CurrentState, Dict[str, Any]]]:
        device_state = device.state
        if device_state is None:
            _LOGGER.warning(
                f"Device with ID '{device.device_id}' partial state data retrieved, "
                f"but no initial data has yet been received. Skipping...",
            )

            return None

        _LOGGER.debug(
            f"Appending stats data for device with ID '{device.device_id}'"
        )

        args = {}

        if "x" in data:
            args["latitude"] = data["x"]
        if "y" in data:
            args["longitude"] = data["y"]
        if "speed" in data:
            args["speed"] = data["speed"]
        if "bit_state_1" in data:
            args["bit_state"] = BitStatus(int(data["bit_state_1"]))
        if "engine_rpm" in data:
            args["engine_rpm"] = data["engine_rpm"]
        if "engine_temp" in data:
            args["engine_temperature"] = data["engine_temp"]
        if "cabin_temp" in data:
            args["interior_temperature"] = data["cabin_temp"]
        if "out_temp" in data:
            args["exterior_temperature"] = data["out_temp"]
        if "balance" in data:
            args["balance"] = (
                BalanceState(
                    value=data["balance"]["value"],
                    currency=data["balance"]["cur"],
                )
                if data["balance"]
                else None
            )
        if "balance1" in data:
            args["balance_other"] = (
                BalanceState(
                    value=data["balance1"]["value"],
                    currency=data["balance1"]["cur"],
                )
                if data["balance1"]
                else None
            )
        if "mileage" in data:
            args["mileage"] = data["mileage"]
        if "mileage_CAN" in data:
            args["can_mileage"] = data["mileage_CAN"]
        if "metka" in data:
            args["tag_number"] = data["metka"]
        if "brelok" in data:
            args["key_number"] = data["brelok"]
        if "move" in data:
            args["is_moving"] = data["move"]
        if "evaq" in data:
            args["is_evacuating"] = data["evaq"]
        if "fuel" in data:
            args["fuel"] = data["fuel"]
        if "gsm_level" in data:
            args["gsm_level"] = data["gsm_level"]
        if "relay" in data:
            args["relay"] = data["relay"]
        if "voltage" in data:
            args["voltage"] = data["voltage"]
        if "state" in data:
            args["state_timestamp"] = data["state"]
        if "state_utc" in data:
            args["state_timestamp_utc"] = data["state_utc"]
        if "online" in data:
            args["online_timestamp"] = data["online"]
        if "online_utc" in data:
            args["online_timestamp_utc"] = data["online_utc"]
        if "setting_utc" in data:
            args["settings_timestamp_utc"] = data["setting_utc"]
        if "command_utc" in data:
            args["command_timestamp_utc"] = data["command_utc"]
        if "active_sim" in data:
            args["active_sim"] = data["active_sim"]
        if "track_remains" in data:
            args["tracking_remaining"] = data["track_remains"]
        if "lock_x" in data:
            args["lock_latitude"] = data["lock_x"] / 1000000
        if "lock_y" in data:
            args["lock_longitude"] = data["lock_y"] / 1000000
        if "rot" in data:
            args["rotation"] = data["rot"]
        if "CAN_TMPS_forvard_left" in data:
            args["can_tpms_front_left"] = data["CAN_TMPS_forvard_left"]
        if "CAN_TMPS_forvard_right" in data:
            args["can_tpms_front_right"] = data["CAN_TMPS_forvard_right"]
        if "CAN_TMPS_back_left" in data:
            args["can_tpms_back_left"] = data["CAN_TMPS_back_left"]
        if "CAN_TMPS_back_right" in data:
            args["can_tpms_back_right"] = data["CAN_TMPS_back_right"]
        if "CAN_driver_glass" in data:
            args["can_glass_front_left"] = data["CAN_driver_glass"]
        if "CAN_passenger_glass" in data:
            args["can_glass_front_right"] = data["CAN_passenger_glass"]
        if "CAN_back_left_glass" in data:
            args["can_glass_back_left"] = data["CAN_back_left_glass"]
        if "CAN_back_right_glass" in data:
            args["can_glass_back_right"] = data["CAN_back_right_glass"]
        if "CAN_low_liquid" in data:
            args["can_low_liquid_warning"] = data["CAN_low_liquid"]
        if "CAN_mileage_by_battery" in data:
            args["can_mileage_by_battery"] = data["CAN_mileage_by_battery"]
        if "CAN_mileage_to_empty" in data:
            args["can_mileage_until_empty"] = data["CAN_mileage_to_empty"]
        if "charging_connect" in data:
            args["ev_charging_connected"] = data["charging_connect"]
        if "charging_slow" in data:
            args["ev_charging_slow"] = data["charging_slow"]
        if "charging_fast" in data:
            args["ev_charging_fast"] = data["charging_fast"]
        if "ev_status_ready" in data:
            args["ev_status_ready"] = data["ev_status_ready"]
        if "battery_temperature" in data:
            args["battery_temperature"] = data["battery_temperature"]
        if "tanks" in data:
            args["fuel_tanks"] = self.parse_fuel_tanks(data["tanks"])

        new_state = attr.evolve(device_state, **args)
        device.state = new_state

        return new_state, args

    def _process_ws_event(
        self, device: "PandoraOnlineDevice", data: Mapping[str, Any]
    ) -> TrackingEvent:
        return TrackingEvent(
            identifier=data["id"],
            bit_state=BitStatus(int(data["bit_state_1"])),
            cabin_temperature=data["cabin_temp"],
            engine_rpm=data["engine_rpm"],
            engine_temperature=data["engine_temp"],
            event_id_primary=data["eventid1"],
            event_id_secondary=data["eventid2"],
            fuel=data["fuel"],
            gsm_level=data["gsm_level"],
            exterior_temperature=data["out_temp"],
            timestamp=data["dtime"],
            recorded_timestamp=data["dtime_rec"],
            voltage=data["voltage"],
            latitude=data["x"],
            longitude=data["y"],
        )

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
            identifier=device.device_id,
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

    async def async_listen_for_updates(
        self,
        *,
        state_callback: Optional[
            Callable[
                ["PandoraOnlineDevice", CurrentState, Mapping[str, Any]],
                Awaitable[None],
            ]
        ] = None,
        command_callback: Optional[
            Callable[
                ["PandoraOnlineDevice", int, int, Any],
                Awaitable[None],
            ]
        ] = None,
        event_callback: Optional[
            Callable[
                ["PandoraOnlineDevice", TrackingEvent],
                Awaitable[None],
            ]
        ] = None,
        point_callback: Optional[
            Callable[
                ["PandoraOnlineDevice", TrackingPoint],
                Awaitable[None],
            ]
        ] = None,
        auto_restart: bool = True,
    ) -> None:
        try:

            while True:
                try:
                    async with self._session.ws_connect(
                        self.BASE_URL
                        + f"/api/v4/updates/ws?access_token={self._access_token}"
                    ) as ws:
                        _LOGGER.debug(f"[{self}] WebSockets connected")

                        while True:
                            try:
                                async with async_timeout.timeout(180):
                                    msg = await ws.receive()
                            except asyncio.TimeoutError:
                                _LOGGER.debug(
                                    f"[{self}] Timed out (WebSockets may be dead)"
                                )
                                # @TODO: think of a better way to check this
                                break

                            _LOGGER.debug(f"[{self}] Current message: {msg}")

                            if msg.type == aiohttp.WSMsgType.closed:
                                _LOGGER.debug(
                                    f"[{self}] WebSockets message channel is closed"
                                )
                                break

                            elif msg.type == aiohttp.WSMsgType.error:
                                _LOGGER.error(
                                    "WebSockets message channel encountered an error: %s",
                                    msg.data,
                                )
                                break

                            elif msg.type == aiohttp.WSMsgType.text:
                                callback_coro = None

                                contents = json.loads(msg.data)
                                type_, data = (
                                    contents["type"],
                                    contents["data"],
                                )

                                device_id = data["dev_id"]
                                device = self.get_device(device_id)

                                try:
                                    if type_ == "initial-state":
                                        result = (
                                            self._process_ws_initial_state(
                                                device, data
                                            )
                                        )
                                        if state_callback:
                                            callback_coro = state_callback(
                                                device, *result
                                            )

                                    elif type_ == "state":
                                        result = self._process_ws_state(
                                            device, data
                                        )
                                        if (
                                            result is not None
                                            and state_callback
                                        ):
                                            callback_coro = state_callback(
                                                device, *result
                                            )

                                    elif type_ == "point":
                                        result = self._process_ws_point(
                                            device, data
                                        )
                                        if point_callback:
                                            callback_coro = point_callback(
                                                device, result
                                            )

                                    elif type_ == "command":
                                        (
                                            command_id,
                                            result,
                                            reply,
                                        ) = self._process_ws_command(
                                            device, data
                                        )

                                        if command_callback:
                                            callback_coro = command_callback(
                                                device,
                                                command_id,
                                                result,
                                                reply,
                                            )

                                    elif type_ == "event":
                                        tracking_event = (
                                            self._process_ws_event(
                                                device, data
                                            )
                                        )

                                        if event_callback:
                                            callback_coro = event_callback(
                                                device, tracking_event
                                            )

                                    else:
                                        _LOGGER.warning(
                                            f"Unknown response type '{type_}' with data '{data}'"
                                        )
                                except BaseException as e:
                                    _LOGGER.fatal(
                                        f"Error during preliminary response processing "
                                        f"with message type {type_}: {repr(e)}\nPlease, "
                                        f"report this error to the developer immediately!"
                                    )
                                    continue

                                if callback_coro is not None:
                                    try:
                                        await asyncio.shield(callback_coro)
                                    except asyncio.CancelledError:
                                        raise
                                    except BaseException as e:
                                        _LOGGER.exception(
                                            f"[{self}] Error during "
                                            f"callback handling: {e}"
                                        )

                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    OSError,
                ) as e:
                    _LOGGER.error(f"[{self}] Error during listening: {e}")
                    if not auto_restart:
                        raise

                if not auto_restart:
                    break

                _LOGGER.debug(f"[{self}] Will restart listener in 10 seconds")
                await asyncio.sleep(10)
                _LOGGER.debug(f"[{self}] Reauthenticating before restarting")
                try:
                    await self.async_authenticate()
                except asyncio.CancelledError:
                    raise
                except BaseException as e:
                    _LOGGER.exception(
                        f"[{self}] Error during reauthentication: {e}"
                    )

            _LOGGER.info(
                f"[{self}] Restarting listener in 3 seconds automatically per instruction"
            )
            await asyncio.sleep(3)

        except asyncio.CancelledError:
            _LOGGER.debug(f"[{self}] WebSockets stopped")
            return


class PandoraOnlineDevice:
    """Models state and remote services of one vehicle.

    :param account: ConnectedDrive account this vehicle belongs to
    :param attributes: attributes of the vehicle as provided by the server
    """

    def __init__(
        self,
        account: PandoraOnlineAccount,
        attributes: Mapping[str, Any],
        current_state: Optional[CurrentState] = None,
        control_timeout: float = DEFAULT_CONTROL_TIMEOUT,
    ) -> None:
        """
        Instantiate vehicle object.
        :param account:
        """
        self._account = account
        self._control_future: Optional[asyncio.Future] = None
        self._features = None
        self._attributes = attributes
        self._current_state = current_state
        self._last_point: Optional[TrackingPoint] = None

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
    def state(self) -> Optional[CurrentState]:
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
    def last_point(self) -> Optional[TrackingPoint]:
        return self._last_point

    @last_point.setter
    def last_point(self, value: Optional[TrackingPoint]) -> None:
        if value is None:
            self._last_point = None
            return

        if value.identifier != self.device_id:
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
                raise CommandExecutionException("timeout executing command")

        _LOGGER.debug("Command executed successfully")

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
            CommandID.TURN_ON_COOLANT_HEATER, ensure_complete
        )

    async def async_remote_turn_off_coolant_heater(
        self, ensure_complete: bool = True
    ):
        return await self.async_remote_command(
            CommandID.TURN_OFF_COOLANT_HEATER, ensure_complete
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

    def release_control_lock(self, error: Optional[Any] = None) -> None:
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
        return current_state is not None and bool(
            current_state.online_timestamp
        )

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
    def features(self) -> Optional[Features]:
        if self._features is None:
            self._features = Features.from_dict(self._attributes["features"])
        return self._features

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
    def color(self) -> Optional[str]:
        return self._attributes.get("color")

    @property
    def car_type_id(self) -> Optional[int]:
        return self._attributes.get("car_type")

    @property
    def car_type(self) -> Optional[str]:
        car_type = self.car_type_id
        if car_type is None:
            return None
        if car_type == 1:
            return "truck"
        if car_type == 2:
            return "moto"
        return "car"

    @property
    def photo_id(self) -> Optional[str]:
        return self._attributes.get("photo")

    @property
    def photo_url(self) -> Optional[str]:
        photo_id = self.photo_id
        if not photo_id:
            return photo_id

        return f"/images/avatars/{photo_id}.jpg"


class PandoraOnlineException(Exception):
    """Base class for Pandora Car Alarm System exceptions"""

    pass


class RequestException(PandoraOnlineException):
    """Request-related exception"""

    pass


class AuthenticationException(RequestException):
    """Authentication-related exception"""

    pass


class CommandExecutionException(RequestException):
    pass
