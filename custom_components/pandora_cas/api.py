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
from types import MappingProxyType
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
    Dict,
    Final,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
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

    # Various commands
    TRIGGER_HORN = 23
    TRIGGER_LIGHT = 24
    TRIGGER_TRUNK = 34
    CHECK = 255

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
    BRAKES_ENGAGED = pow(
        2, 28
    )  # Any brake system is engaged #@TODO: description might be invalid
    BLOCK_HEATER_ACTIVE = pow(2, 29)  # Pre-start heater active
    ACTIVE_SECURITY = pow(2, 30)  # Active security active
    BLOCK_HEATER_ENABLED = pow(2, 31)  # Pre-start heater function is available
    # ... = pow(2, 32) # ?
    EVACUATION_MODE_ACTIVE = pow(2, 33)  # Evacuation mode active
    SERVICE_MODE_ACTIVE = pow(2, 34)  # Service mode active
    STAY_HOME_ACTIVE = pow(2, 35)  # Stay home mode active
    # (...) = (pow(2, 36), ..., pow(2, 60) # ?
    SECURITY_TAG_ENFORCED = pow(2, 61)  # Enforce security tags


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


@attr.s(kw_only=True, frozen=True, slots=True)
class BalanceState:
    value: float = attr.ib(converter=float)
    currency: str = attr.ib()

    @classmethod
    def from_json(cls, data: Mapping[str, Any]):
        return cls(
            value=data["value"],
            currency=data["cur"],
        )


_T = TypeVar("_T")


def _empty_is_none(x: _T) -> Optional[_T]:
    return x or None


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
    balance: BalanceState = attr.ib()
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
    phone_other: Optional[str] = attr.ib(default=None, converter=_empty_is_none)
    active_sim: int = attr.ib()
    tracking_remaining: Optional[float] = attr.ib(
        default=None, converter=_empty_is_none
    )

    # undecoded parameters
    smeter: int = attr.ib(default=None)
    tconsum: int = attr.ib(default=None)
    loadaxis: Any = attr.ib(default=None)
    land: int = attr.ib(default=None)
    bunker: int = attr.ib(default=None)
    ex_status: int = attr.ib(default=None)
    balance_other: Any = attr.ib(default=None)
    fuel_tanks: Collection[Any] = attr.ib(default=None)

    state_timestamp: int = attr.ib()
    state_timestamp_utc: int = attr.ib()
    online_timestamp: int = attr.ib()
    online_timestamp_utc: int = attr.ib()
    settings_timestamp_utc: int = attr.ib()
    command_timestamp_utc: int = attr.ib()

    @property
    def direction(self) -> str:
        """Textual interpretation of rotation."""
        sides = [
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
        ]
        return sides[round(self.rotation / (360 / len(sides))) % len(sides)]

    @classmethod
    def args_from_json(cls, data: Mapping[str, Any]) -> Dict[str, Any]:
        args = dict()

        return args

    @classmethod
    def from_json(cls, data: Mapping[str, Any]):
        return cls(**cls.args_from_json(data))

    def append_json(self, data: Mapping[str, Any]):
        args = self.args_from_json(data)
        return self.__class__(
            **{
                key: args[key] if key in args else getattr(self, key)
                for key in attr.fields_dict(self.__class__)
            }
        )


class PandoraOnlineAccount:
    """Pandora Online account interface."""

    BASE_URL = "https://pro.p-on.ru"

    def __init__(
        self,
        username: str,
        password: str,
        access_token: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Instantiate Pandora Online account object.
        :param username: Account username
        :param password: Account password
        :param access_token: Access token (optional)
        :param user_agent: (optional) Specify differing user agent
        """
        self._username = username
        self._password = password
        self._access_token = access_token
        self._user_agent = user_agent
        self._user_agent = user_agent if user_agent else DEFAULT_USER_AGENT
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

    def get_device(self, device_id: Union[int, str]) -> Optional["PandoraOnlineDevice"]:
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
                    "unexpected status: %d" % (response.status,)
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
                raise PandoraOnlineException(f"Error fetching access token: {e}")
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
                'Authentication successful for username "%s"!' % (self._username,)
            )
            self._access_token = access_token

    async def async_update_vehicles(self):
        """Retrieve and cache list of vehicles for the account."""
        access_token = self._access_token
        if access_token is None:
            raise PandoraOnlineException("Account is not authenticated")

        _LOGGER.debug('Updating vehicle list for username "%s"' % (self._username,))

        async with self._session.get(
            self.BASE_URL + "/api/devices",
            params={"access_token": self._access_token},
        ) as response:
            devices_data = await self._handle_response(response)
            _LOGGER.debug("retrieved devices: %s" % devices_data)

        new_devices_list = []

        for device_attributes in devices_data:
            device_id = int(device_attributes["id"])
            device_object = self.get_device(device_id)

            if device_object is None:
                device_object = PandoraOnlineDevice(self, device_attributes)
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

        _LOGGER.debug('Sending command "%d" to device "%d"' % (command_id, device_id))

        async with self._session.post(
            self.BASE_URL + "/api/devices/command",
            data={"id": device_id, "command": int(command_id)},
            params={"access_token": self._access_token},
        ) as response:
            command_result = await self._handle_response(response)
            status = command_result.get("action_result", {}).get(str(device_id))

            if status != "sent":
                raise CommandExecutionException("could not execute command", status)

            _LOGGER.debug('Command "%d" sent to device "%d"' % (command_id, device_id))

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
                    device_object.stats = stats_data
                    updated_device_ids.add(device_object.device_id)
                else:
                    _LOGGER.warning(
                        'Device with ID "%s" stats data retrieved, '
                        "but no object created yet. Skipping..." % (device_id,)
                    )

        self._last_update = int(content["ts"])

        return content, updated_device_ids

    async def async_listen_for_updates(
        self,
        update_callback: Callable[
            ["PandoraOnlineDevice", Collection[str]], Awaitable[None]
        ],
    ) -> None:
        access_token = self._access_token
        if access_token is None:
            raise PandoraOnlineException("Account is not authenticated")

        ws = await self._session.ws_connect(
            self.BASE_URL + f"/api/v4/updates/ws?access_token={access_token}"
        )

        while True:
            msg = await ws.receive()

            if msg.type == aiohttp.WSMsgType.closed:
                break

            elif msg.type == aiohttp.WSMsgType.error:
                break

            elif msg.type == aiohttp.WSMsgType.text:
                contents = json.loads(msg.data)
                type_, data = contents["type"], contents["data"]

                if type_ == "initial-state":
                    device_id = data["dev_id"]
                    device_object = self.get_device(device_id)

                    if device_object:
                        _LOGGER.debug(
                            f"Updating stats data for device with ID '{device_id}'"
                        )
                        device_object.state = CurrentState(
                            identifier=data["id"],
                            latitude=data["x"],
                            longitude=data["y"],
                            speed=data["speed"],
                            bit_state=BitStatus(data["bit_state_1"]),
                            engine_rpm=data["engine_rpm"],
                            engine_temperature=data["engine_temp"],
                            interior_temperature=data["cabin_temp"],
                            exterior_temperature=data["out_temp"],
                            balance=BalanceState.from_json(data["balance"]),
                            balance_other=data["balance1"],
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
                        )

                        await update_callback(
                            device_object,
                            attr.fields_dict(CurrentState).keys(),
                        )

                    else:
                        _LOGGER.warning(
                            f"Device with ID '{device_id}' stats data retrieved, "
                            f"but no object created yet. Skipping...",
                        )

                elif type_ == "state":
                    device_id = data["dev_id"]
                    device_object = self.get_device(device_id)

                    if device_object:
                        device_state = device_object.state
                        if device_state:
                            _LOGGER.debug(
                                f"Appending stats data for device with ID '{device_id}'"
                            )

                            args = {}

                            if "x" in data:
                                args["latitude"] = data["x"]
                            if "y" in data:
                                args["longitude"] = data["y"]
                            if "speed" in data:
                                args["speed"] = data["speed"]
                            if "bit_state_1" in data:
                                args["bit_state"] = BitStatus(data["bit_state_1"])
                            if "engine_rpm" in data:
                                args["engine_rpm"] = data["engine_rpm"]
                            if "engine_temp" in data:
                                args["engine_temperature"] = data["engine_temp"]
                            if "cabin_temp" in data:
                                args["interior_temperature"] = data["cabin_temp"]
                            if "out_temp" in data:
                                args["exterior_temperature"] = data["out_temp"]
                            if "balance" in data:
                                args["balance"] = BalanceState.from_json(
                                    data["balance"]
                                )
                            if "balance1" in data:
                                args["balance_other"] = data["balance1"]
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

                            device_object.state = attr.evolve(device_state, **args)

                            await update_callback(
                                device_object,
                                attr.fields_dict(CurrentState).keys(),
                            )

                        else:
                            _LOGGER.warning(
                                f"Device with ID '{device_id}' partial state data retrieved, "
                                f"but no initial data has yet been received. Skipping...",
                            )

                    else:
                        _LOGGER.warning(
                            f"Device with ID '{device_id}' partial stats data retrieved, "
                            f"but no object created yet. Skipping...",
                        )

                else:
                    _LOGGER.warning(
                        f"Unknown response type '{type_}' with data '{data}'"
                    )


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

        # Control timeout setting
        self.control_timeout = control_timeout

    def __repr__(self):
        return "<" + str(self) + ">"

    def __str__(self) -> str:
        """Use the name as identifier for the vehicle."""
        return '%s[id=%d, name="%s", account=%r]' % (
            self.__class__.__name__,
            self.device_id,
            self.name,
            self._account,
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
                and old_state.command_timestamp_utc < value.command_timestamp_utc
            ):
                self._control_future.set_result(True)
                self._control_future = None

        self._current_state = value

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
                await asyncio.wait_for(self._control_future, self.control_timeout)
                self._control_future.result()

            except asyncio.TimeoutError:
                raise CommandExecutionException("timeout executing command")

        _LOGGER.debug("Command executed successfully")

    # Lock/unlock toggles
    async def async_remote_lock(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.LOCK, ensure_complete)

    async def async_remote_unlock(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.UNLOCK, ensure_complete)

    # Engine toggle
    async def async_remote_start_engine(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.START_ENGINE, ensure_complete)

    async def async_remote_stop_engine(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.STOP_ENGINE, ensure_complete)

    # Tracking toggle
    async def async_remote_enable_tracking(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.ENABLE_TRACKING, ensure_complete
        )

    async def async_remote_disable_tracking(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.DISABLE_TRACKING, ensure_complete
        )

    # Active security toggle
    async def async_enable_active_security(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.ENABLE_ACTIVE_SECURITY, ensure_complete
        )

    async def async_disable_active_security(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.DISABLE_ACTIVE_SECURITY, ensure_complete
        )

    # Coolant heater toggle
    async def async_remote_turn_on_coolant_heater(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TURN_ON_COOLANT_HEATER, ensure_complete
        )

    async def async_remote_turn_off_coolant_heater(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TURN_OFF_COOLANT_HEATER, ensure_complete
        )

    # External (timer_ channel toggle
    async def async_remote_turn_on_ext_channel(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TURN_ON_EXT_CHANNEL, ensure_complete
        )

    async def async_remote_turn_off_ext_channel(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.TURN_OFF_EXT_CHANNEL, ensure_complete
        )

    # Service mode toggle
    async def async_remote_enable_service_mode(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.ENABLE_SERVICE_MODE, ensure_complete
        )

    async def async_remote_disable_service_mode(self, ensure_complete: bool = True):
        return await self.async_remote_command(
            CommandID.DISABLE_SERVICE_MODE, ensure_complete
        )

    # Various commands
    async def async_remote_trigger_horn(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TRIGGER_HORN, ensure_complete)

    async def async_remote_trigger_light(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TRIGGER_LIGHT, ensure_complete)

    async def async_remote_trigger_trunk(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TRIGGER_TRUNK, ensure_complete)

    @property
    def control_busy(self) -> bool:
        """Returns whether device is currently busy executing command."""
        return not (self._control_future is None or self._control_future.done())

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
        return current_state is not None and bool(current_state.online_timestamp)

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
