"""API interface for Pandora Car Alarm System."""
__all__ = [
    # Basic entities
    'PandoraOnlineAccount', 'PandoraOnlineDevice',

    # Enumerations and flags
    'CommandID', 'Features', 'EventType', 'AlertType', 'BitStatus',

    # Exceptions
    'PandoraOnlineException', 'AuthenticationException', 'RequestException', 'CommandExecutionException',

    # Constants
    'DEFAULT_USER_AGENT', 'DEFAULT_CONTROL_TIMEOUT',
]
import asyncio
import logging
from enum import IntEnum, IntFlag, Flag, auto
from json import JSONDecodeError
from random import randint
from types import MappingProxyType
from typing import Dict, Any, Optional, Mapping, Union, List, Tuple

import aiohttp

_LOGGER = logging.getLogger(__name__)

#: default user agent for use in requests
DEFAULT_USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/60.0.3112.113 Safari/537.36')

#: timeout to consider command execution unsuccessful
DEFAULT_CONTROL_TIMEOUT = 30


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
    """Enumeration to decode `bit_status_1` state parameter."""
    LOCKED = 1
    ALARM = 2
    ENGINE_RUNNING = 4
    IGNITION = 8
    # AUTOSTART_INIT = 16
    HANDS_FREE_LOCKED = 32
    HANDS_FREE_UNLOCKED = 64
    GSM_ACTIVE = 128
    GPS_ACTIVE = 256
    TRACKING_ENABLED = 512
    IMMOBILIZER_ENABLED = 1024
    EXT_SENSOR_ALERT_ZONE = 2048
    EXT_SENSOR_MAIN_ZONE = 4096
    SENSOR_ALERT_ZONE = 8192
    SENSOR_MAIN_ZONE = 16384
    AUTOSTART = 32768
    SMS = 65536
    CALL = 131072
    LIGHT = 262144
    SOUND1 = 524288
    SOUND2 = 1048576
    DOOR_FRONT_LEFT_OPEN = 2097152
    DOOR_FRONT_RIGHT_OPEN = 4194304
    DOOR_BACK_LEFT_OPEN = 8388608
    DOOR_BACK_RIGHT_OPEN = 16777216
    TRUNK_OPEN = 33554432
    HOOD_OPEN = 67108864
    HANDBRAKE_ENGAGED = 134217728
    BRAKES_ENGAGED = 268435456
    COOLANT_HEATER = 536870912
    ACTIVE_SECURITY = 1073741824


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
    def from_dict(cls, features_dict: Dict[str, Union[bool, int]]) -> Optional['Features']:
        result = None
        for key, flag in {'active_security': cls.ACTIVE_SECURITY,
                          'auto_check': cls.AUTO_CHECK,
                          'autostart': cls.AUTO_START,
                          'beep': cls.BEEPER,
                          'bluetooth': cls.BLUETOOTH,
                          'channel': cls.EXT_CHANNEL,
                          'connection': cls.NETWORK,
                          'custom_phones': cls.CUSTOM_PHONES,
                          'events': cls.EVENTS,
                          'extend_props': cls.EXTENDED_PROPERTIES,
                          'heater': cls.COOLANT_HEATER,
                          'keep_alive': cls.KEEP_ALIVE,
                          'light': cls.LIGHT_TOGGLE,
                          'notification': cls.NOTIFICATIONS,
                          'schedule': cls.SCHEDULE,
                          'sensors': cls.SENSORS,
                          'tracking': cls.TRACKING,
                          'trunk': cls.TRUNK_TRIGGER}.items():
            if features_dict.get(key):
                if result is None:
                    result = flag
                else:
                    result |= flag

        return result


class PandoraOnlineAccount:
    """Pandora Online account interface."""

    BASE_URL = "https://pro.p-on.ru"

    def __init__(self, username: str, password: str, user_agent: Optional[str] = None) -> None:
        """
        Instantiate Pandora Online account object.
        :param username: Account username
        :param password: Account password
        :param user_agent: (optional) Specify differing user agent
        """
        self._username = username
        self._password = password
        self._user_agent = user_agent
        self._cookie_jar = aiohttp.CookieJar()
        self._user_agent = user_agent if user_agent else DEFAULT_USER_AGENT

        #: last update timestamp
        self._last_update = -1

        #: properties generated upon authentication
        self._session_id = None
        self._user_id = None

        #: list of vehicles associated with this account.
        self._devices: List[PandoraOnlineDevice] = list()

    def __repr__(self):
        """Retrieve representation of account object"""
        return '<' + str(self) + '>'

    def __str__(self):
        return '%s[username="%s"]' % (
            self.__class__.__name__,
            self._username
        )

    # Basic properties
    @property
    def username(self) -> str:
        """Username accessor."""
        return self._username

    @property
    def last_update(self) -> int:
        return self._last_update

    @property
    def devices(self) -> Tuple['PandoraOnlineDevice']:
        """Devices (immutable) accessor."""
        return tuple(self._devices)

    def get_device(self, device_id: Union[int, str]) -> Optional['PandoraOnlineDevice']:
        _device_id = int(device_id)
        for device in self._devices:
            if _device_id == device.device_id:
                return device

    # Remote action handlers
    def _init_async_remote_session(self, **kwargs) -> aiohttp.ClientSession:
        """Shorthand method to retrieve prepared session"""
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': self.BASE_URL,
            'Origin': self.BASE_URL,
            'User-Agent': self._user_agent,
        }
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
            del kwargs['headers']

        return aiohttp.ClientSession(
            cookie_jar=self._cookie_jar,
            headers=headers,
            **kwargs
        )

    async def _handle_response(self, response: aiohttp.ClientResponse, expected_status: int = 200,
                               check_status_field: Union[bool, str] = False):
        try:
            if response.status != expected_status:
                raise RequestException('unexpected status: %d' % (response.status,)) from None

            content = await response.json()

            if check_status_field and content.get('status') == \
                    ('success' if check_status_field is True else check_status_field):
                raise RequestException('invalid response', content) from None

            return content

        except JSONDecodeError:
            raise RequestException('unknown server response format', await response.text()) from None

        except aiohttp.ClientConnectionError:
            raise RequestException('connection error') from None

        except aiohttp.ClientResponseError:
            raise RequestException('invalid server response') from None

        except aiohttp.ClientError as e:
            raise RequestException('HTTP client error: %s' % (e,)) from None

    # Requests
    async def async_authenticate(self, session: Optional[aiohttp.ClientSession] = None):
        if session is None:
            async with self._init_async_remote_session() as session:
                return await self.async_authenticate(session)

        _LOGGER.debug('Authenticating with username "%s"' % (self._username,))

        session.cookie_jar.clear()
        url = self.BASE_URL + '/api/users/login'
        request_headers = {
            'User-Agent': self._user_agent,
            'Referer': self.BASE_URL + '/login',
            'Origin': self.BASE_URL
        }
        request_data = {
            'login': self._username,
            'password': self._password,
            'lang': 'ru',
        }

        async with session.post(url, headers=request_headers, data=request_data) as response:
            try:
                await self._handle_response(response)
            except RequestException as e:
                raise AuthenticationException(*e.args) from None

            _LOGGER.info('Authentication successful for username "%s"!' % (self._username,))
            return

    async def async_update_vehicles(self, session: Optional[aiohttp.ClientSession] = None):
        """Retrieve and cache list of vehicles for the account."""

        if session is None:
            async with self._init_async_remote_session() as session:
                return await self.async_update_vehicles(session)

        _LOGGER.debug('Updating vehicle list for username "%s"' % (self._username,))
        async with session.get(self.BASE_URL + '/api/devices') as response:
            devices_data = await self._handle_response(response)
            _LOGGER.debug('retrieved devices: %s' % devices_data)

        new_devices_list = []

        for device_attributes in devices_data:
            device_id = int(device_attributes['id'])
            device_object = self.get_device(device_id)

            if device_object is None:
                device_object = PandoraOnlineDevice(self, device_attributes)
            else:
                device_object.attributes = device_attributes

            new_devices_list.append(device_object)

        self._devices = new_devices_list

    async def async_remote_alive(self, click_count: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None):
        if session is None:
            async with self._init_async_remote_session() as session:
                return await self.async_remote_alive(session=session)

        _LOGGER.debug('Performing alive request')
        async with session.post(self.BASE_URL + '/api/iamalive', data={
            'num_click': randint(0, 30) if click_count is None else click_count,
        }) as response:
            await self._handle_response(response)

    async def async_remote_command(self, device_id: int, command_id: Union[int, 'CommandID'],
                                   session: Optional[aiohttp.ClientSession] = None):
        if session is None:
            async with self._init_async_remote_session() as session:
                return await self.async_remote_command(device_id, command_id, session=session)

        _LOGGER.debug('Sending command "%d" to device "%d"' % (command_id, device_id))

        async with session.post(self.BASE_URL + '/api/devices/command', data={
            'id': device_id,
            'command': int(command_id),
        }) as response:
            command_result = await self._handle_response(response)
            status = command_result.get('action_result', {}).get(str(device_id))

            if status != 'sent':
                raise CommandExecutionException('could not execute command', status)

            _LOGGER.debug('Command "%d" sent to device "%d"' % (command_id, device_id))

    async def async_fetch_changes(self, timestamp: Optional[int] = None,
                                  session: Optional[aiohttp.ClientSession] = None):
        """
        Fetch latest changes from update server.
        :param timestamp:
        :param session:
        :return: (New data, Set of updated device IDs)
        """
        if session is None:
            async with self._init_async_remote_session() as session:
                return await self.async_fetch_changes(session=session)

        _timestamp = self._last_update if timestamp is None else timestamp
        async with session.get(self.BASE_URL + '/api/updates', params={'ts': _timestamp}) as response:
            content: Dict[str, Any] = await self._handle_response(response)

        updated_device_ids = set()

        # Time updates
        if content.get('time'):
            for device_id, times_data in content['time'].items():
                device_object = self.get_device(device_id)
                if device_object:
                    _LOGGER.debug('Updating times data for device %s' % (device_object,))
                    device_object.times = times_data
                    updated_device_ids.add(device_object.device_id)
                else:
                    _LOGGER.warning('Device with ID "%s" times data retrieved, but no object created yet. Skipping...'
                                    % (device_id,))

        # Stats updates
        if content.get('stats'):
            for device_id, stats_data in content['stats'].items():
                device_object = self.get_device(device_id)
                if device_object:
                    _LOGGER.debug('Updating stats data for device %s' % (device_object,))
                    device_object.stats = stats_data
                    updated_device_ids.add(device_object.device_id)
                else:
                    _LOGGER.warning('Device with ID "%s" stats data retrieved, but no object created yet. Skipping...'
                                    % (device_id,))

        self._last_update = int(content['ts'])

        return content, updated_device_ids


class PandoraOnlineDevice:
    """Models state and remote services of one vehicle.

    :param account: ConnectedDrive account this vehicle belongs to
    :param attributes: attributes of the vehicle as provided by the server
    """

    def __init__(self, account: PandoraOnlineAccount, attributes: Mapping[str, Any],
                 vehicle_stats: Optional[Mapping[str, Any]] = None,
                 control_timeout: float = DEFAULT_CONTROL_TIMEOUT,
                 last_times: Optional[Mapping[str, int]] = None) -> None:
        """
        Instantiate vehicle object.
        :param account:
        :param attributes:
        """
        self._account = account
        self._attributes = dict(attributes)
        self._control_future: Optional[asyncio.Future] = None
        self._stats = None if vehicle_stats is None else dict(vehicle_stats)
        self._features = None
        self._bit_status = None

        # Initialize last times dictionary
        _init_last_times = dict.fromkeys(['command', 'setting', 'online', 'onlined'], -1)
        if last_times is not None:
            _init_last_times.update(last_times)
        self._last_times = _init_last_times

        # Control timeout setting
        self.control_timeout = control_timeout

    def __repr__(self):
        return '<' + str(self) + '>'

    def __str__(self) -> str:
        """Use the name as identifier for the vehicle."""
        return '%s[id=%d, name="%s", account=%r]' % (
            self.__class__.__name__,
            self.device_id,
            self.name,
            self._account
        )

    # Remote command execution section
    async def async_remote_command(self,
                                   command_id: Union[int, CommandID],
                                   ensure_complete: bool = True,
                                   session: Optional[aiohttp.ClientSession] = None):
        """Proxy method to execute commands on corresponding vehicle object"""
        if self.control_busy:
            raise RuntimeError('device is busy executing command')

        if ensure_complete:
            self._control_future = asyncio.Future()

        await self._account.async_remote_command(self.device_id, command_id, session)

        if ensure_complete:
            try:
                _LOGGER.debug('Ensuring command completion (timeout: %d seconds)' % (self.control_timeout,))
                await asyncio.wait_for(self._control_future, self.control_timeout)
                self._control_future.result()

            except asyncio.TimeoutError:
                raise CommandExecutionException('timeout executing command')

        _LOGGER.debug('Command executed successfully')

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
        return await self.async_remote_command(CommandID.ENABLE_TRACKING, ensure_complete)

    async def async_remote_disable_tracking(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.DISABLE_TRACKING, ensure_complete)

    # Active security toggle
    async def async_enable_active_security(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.ENABLE_ACTIVE_SECURITY, ensure_complete)

    async def async_disable_active_security(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.DISABLE_ACTIVE_SECURITY, ensure_complete)

    # Coolant heater toggle
    async def async_remote_turn_on_coolant_heater(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TURN_ON_COOLANT_HEATER, ensure_complete)

    async def async_remote_turn_off_coolant_heater(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TURN_OFF_COOLANT_HEATER, ensure_complete)

    # External (timer_ channel toggle
    async def async_remote_turn_on_ext_channel(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TURN_ON_EXT_CHANNEL, ensure_complete)

    async def async_remote_turn_off_ext_channel(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.TURN_OFF_EXT_CHANNEL, ensure_complete)

    # Service mode toggle
    async def async_remote_enable_service_mode(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.ENABLE_SERVICE_MODE, ensure_complete)

    async def async_remote_disable_service_mode(self, ensure_complete: bool = True):
        return await self.async_remote_command(CommandID.DISABLE_SERVICE_MODE, ensure_complete)

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
        return int(self._attributes['id'])

    @property
    def times(self) -> Optional[Mapping[str, Any]]:
        return None if self._last_times is None else MappingProxyType(self._last_times)

    @times.setter
    def times(self, value: Mapping[str, int]):
        if self.control_busy and 'command' in value \
                and value['command'] > self._last_times['command']:
            # Resolve control future
            self._control_future.set_result(True)

        self._last_times.update(value)

    @property
    def is_online(self) -> bool:
        """Returns whether vehicle can be deemed online"""
        return (self._last_times is not None
                and self._stats is not None
                and bool(self._stats['online']))

    # Attributes-related properties
    @property
    def attributes(self) -> Mapping[str, Any]:
        return MappingProxyType(self._attributes)

    @attributes.setter
    def attributes(self, value: Mapping[str, Any]):
        if int(value['id']) != self.device_id:
            raise ValueError('device IDs must match')
        self._attributes = value
        self._features = None

    @property
    def features(self) -> Optional[Features]:
        if self._features is None:
            self._features = Features.from_dict(self._attributes['features'])
        return self._features

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._attributes['name']

    @property
    def model(self) -> str:
        """Get model of the device."""
        return self._attributes['model']

    @property
    def firmware_version(self) -> str:
        return self._attributes['firmware']

    @property
    def voice_version(self) -> str:
        return self._attributes['voice_version']

    @property
    def gps_location(self) -> (float, float):
        """Get the last known position of the vehicle.

        Returns a tuple of (latitude, longitude).
        This only provides data, if the vehicle tracking is enabled!
        """
        return self.latitude, self.longitude

    # Stats-related properties
    @property
    def stats(self) -> Optional[Mapping[str, Any]]:
        return None if self._stats is None else MappingProxyType(self._stats)

    @stats.setter
    def stats(self, value: Mapping[str, Any]):
        self._stats = dict(value)
        self._bit_status = None

    @property
    def status(self) -> BitStatus:
        if self._bit_status is None:
            self._bit_status = BitStatus(self._stats['bit_state_1'])
        return self._bit_status

    @property
    def latitude(self) -> float:
        return float(self._stats['x'])

    @property
    def longitude(self) -> float:
        return float(self._stats['y'])

    @property
    def rotation(self) -> float:
        return float(self._stats['rot'])

    @property
    def direction(self) -> str:
        """Textual interpretation of rotation."""
        sides = ['N', 'NNE', 'NE', 'ENE',
                 'E', 'ESE', 'SE', 'SSE',
                 'S', 'SSW', 'SW', 'WSW',
                 'W', 'WNW', 'NW', 'NNW']
        return sides[round(self.rotation / (360 / len(sides))) % len(sides)]

    @property
    def mileage(self) -> float:
        """Get the mileage of the vehicle.

        Returns a tuple of (value, unit_of_measurement)
        """
        return float(self._stats['mileage'])

    @property
    def mileage_can_bus(self) -> float:
        return float(self._stats['mileage_CAN'])

    @property
    def fuel(self) -> int:
        """Get the remaining fuel of the vehicle.

        Returns a tuple of (value, unit_of_measurement)
        """
        return int(self._stats['fuel'])

    @property
    def interior_temperature(self) -> int:
        """Interior temperature accessor"""
        return int(self._stats['cabin_temp'])

    @property
    def engine_temperature(self) -> int:
        """Engine temperature accessor"""
        return int(self._stats['engine_temp'])

    @property
    def outside_temperature(self) -> int:
        """Outside temperature accessor"""
        return int(self._stats['out_temp'])

    @property
    def speed(self) -> float:
        """Current speed accessor"""
        return round(float(self._stats['speed']), 1)

    @property
    def engine_rpm(self) -> int:
        """Engine revolutions per minute accessor"""
        return int(self._stats['engine_rpm'])

    @property
    def gsm_level(self) -> int:
        """GSM reception level accessor"""
        return int(self._stats['gsm_level'])

    @property
    def is_moving(self) -> bool:
        return bool(self._stats['move'])

    @property
    def battery_voltage(self) -> float:
        """Battery voltage accessor"""
        return round(float(self._stats['voltage']), 1)

    @property
    def active_sim_id(self) -> int:
        return int(self._stats['active_sim'])

    # SIM-related properties
    @property
    def _sim_data(self):
        return self._stats['sims'][self.active_sim_id]

    @property
    def sim_balance(self) -> float:
        return float(self._sim_data['balance']['value'])

    @property
    def sim_currency(self) -> float:
        return float(self._sim_data['balance']['cur'])

    @property
    def sim_number(self) -> float:
        return float(self._sim_data['phoneNumber'])

    # Last time data-related properties
    @property
    def online_since(self) -> int:
        return self._last_times['online']

    # @TODO: research into this parameter
    # @property
    # def onlined(self) -> int:
    #     return self._last_times['onlined']

    @property
    def last_command_time(self) -> int:
        return self._last_times['command']

    @property
    def last_setting_change_time(self) -> int:
        return self._last_times['setting']


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
