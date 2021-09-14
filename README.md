<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/header.png" height="100" alt="Home Assistant + Pandora">

# _Pandora Car Alarm System_ для _Home Assistant_
> Автоматизация управления охранными системами Pandora™ и PanDECT<sup>®</sup> в Home Assistant.
>
> &gt;= Home Assistant 2021.9.4
> 
>[![hacs_badge](https://img.shields.io/badge/HACS-Default-green.svg)](https://github.com/custom-components/hacs)
>[![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
>[![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B4%D0%B0-green.svg)](https://github.com/alryaz/hass-pandora-cas/graphs/commit-activity)  
>
>[![Пожертвование Yandex](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Yandex-red.svg)](https://money.yandex.ru/to/410012369233217)
>[![Пожертвование PayPal](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B6%D0%B5%D1%80%D1%82%D0%B2%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-Paypal-blueviolet.svg)](https://www.paypal.me/alryaz)
  
> Вдохновитель, оригинальный разработчик:  
> [![Репозиторий GitHub](https://img.shields.io/badge/GitHub-turbo--lab%2Fpandora--cas-blue)](https://github.com/turbo-lab/pandora-cas)
> [![Donate](https://img.shields.io/badge/donate-Yandex-orange.svg)](https://money.yandex.ru/to/41001690673042)

> ⚠️ **ВНИМАНИЕ** ⚠️  
> Разработчик в поисках владельцев следующих конфигураций:
> - Pandora UX-4G
> - Pandect X-1800 L
> - Автомобили с отображением TPMS по CAN-шине
>
> При возникновении в тестировании ограниченного (скрытого) функционала, пожалуйста, напишите в мне Telegram: **@alryaz**.

[![Расположение элементов по-умолчанию](https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_default.png)](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_default.png)

Автомобиль тоже может быть частью умного дома. С помощью этого компонента вы сможете отслеживать состояние, управлять
и автоматизировать свой автомобиль, если он оборудован охранной системой Pandora. После настройки ваши
устройства Pandora™ и PanDECT<sup>®</sup> автоматически добавятся в _Home Assistant_.

Компонент реализует доступ к API официального сайта Pandora, `https://pro.p-on.ru`, и реализует часть функционала,
доступного в полной веб-версии. Для настройки Вам следует использовать те же авторизационные данные, что вы используете на сайте Pandora, или в
мобильном приложении [Pandora Online](https://play.google.com/store/apps/details?id=ru.alarmtrade.pandora&hl=ru).

На данный момент компонент поддерживает:
- [Device Tracker](#platform_device_tracker): Местоположение автомобиля.
- [Sensors](#platform_sensor): Температура, скорость, тахометр и т.д.
- [Binary Sensors](#platform_binary_sensor): Статусы открытия, движения, и т.д.
- [Switches](#platform_switch): Работа двигателя, активная охрана, и т.д.
- [Lock](#platform_lock): Постановка на охрану
- [Services](#services_provided): Команды, например: открыть/закрыть, завести/заглушить и др.

## Установка

#### Посредством HACS _(рекомендованый способ)_
1. Установить [HACS](https://hacs.xyz/docs/installation/manual)
1. Установить компонент _Pandora Car Alarm System_
1. Выполнить конфигурацию одним из нижеупомянутых способов
1. _(опционально, для YAML)_ Перезапустить _Home Assistant_

#### Ручная установка
1. Скачать репозиторий:
   1. Посредством Git:  
      ```git clone https://github.com/alryaz/hass-pandora-cas.git hass-pandora-cas```
   1. Через браузер: [ссылка](https://github.com/alryaz/hass-pandora-cas/archive/master.zip)  
      Разархивировать папку `hass-pandora-cas-master` внутри архива в любую папку
1. Перенести содержимое подпапки `custom_components` в аналогичную папку конфигурации _Home Assistant_
   (при отсутствии папки `custom_components` в конфигурации, создать таковую)
1. Выполнить конфигурацию одним из нижеупомянутых способов
1. _(опционально, для YAML)_ Перезапустить _Home Assistant_

## Настройка

### Через интерфейс _"Интеграции"_
Поддерживается базовый функционал конфигурации через веб-интерфейс _Home Assistant_. Конфигурация данным способов
возможна без перезагрузки _Home Assistant_. Для перехода к настройке, выполните следующие действия:

1. Перейдите в раздел _Настройки_ &#10230; _Интеграции_ (`/config/integrations`)
1. Нажмите на круглую кнопку с плюсом внутри в нижнем правом углу экрана
1. Во всплывшем окне, введите в верхнем поле поиска `Pandora`; одним из результатов должен оказаться
   `Pandora Car Alarm System` (с соответствующим логотипом торговой марки _Pandora Car Alarm System_)
1. Нажмите на предложенный результат
1. Введите имя пользователя / пароль в соответствующие поля
1. _(опционально)_ Выставите частоту обновления, введите произвольный _User Agent_
1. Нажмите внизу справа на кнопку `Подтвердить`
   1. В случае обнаружения системой каких-либо ошибок, они будут отображены в окошке
1. Обновление займёт не более 5-10 секунд (проверено на Raspberry Pi 4), элементы в конфигурации по-умолчанию должны
   появится на главном экране (при использовании конфигурациии Lovelace по-умолчанию)

### Базовая конфигурация
Чтобы активировать компонент, добавьте эти строки в файл `configuration.yaml`:

```yaml
# Фрагмент файла configuration.yaml
pandora_cas:
  # Учётная запись на портале p-on.ru / pro.p-on.ru
  password: !secret YOUR_PASSWORD  # обязательно
  username: !secret YOUR_USERNAME  # обязательно
```

#### Использование нескольких учётных записей
Компонент поддерживает работу с несколькими учётными записями.
> Внимание! При добавлении двух учётных записей с одинковыми именами пользователя будет использована первая
> разобранная системой конфигурация.

```yaml
pandora_cas:
    # Первая учётная запись
  - username: !secret YOUR_USERNAME_1  # обязательно
    password: !secret YOUR_PASSWORD_1  # обязательно
    
    # Вторая учётная запись
  - username: !secret YOUR_USERNAME_2  # обязательно
    password: !secret YOUR_PASSWORD_2  # обязательно
```

### Установка дополнительных параметров

```yaml
pandora_cas:
  username: !secret YOUR_USERNAME  # обязательно
  password: !secret YOUR_PASSWORD  # обязательно
  
  # Интервал обновления информации с сайта.
  # Большая частота обновления может повлечь увеличение расходов на передачу данных.
  # По-умолчанию: 60 секунд
  # Минимальное значение: 10 секунд
  #
  polling_interval: 40
  
  # Использование конкретного User Agent в запросах к серверу
  # Может быть полезным, если система отказывается работать с User Agent по-умолчанию.
  #
  user_agent: 'Mozilla/5.0 (X11; Ubuntu; Linux i686 on x86_64; rv:41.0) Gecko/20100101 Firefox/41.0'
  
  # Произвольный формат названий объектов
  # Данная настройка позволяет задать шаблон названий объектов "из коробки"
  # Не распространяется на платформу `device_tracker`
  # Поддерживаются следующие переменные:
  #   - `device_id`: Идентификатор охранной системы
  #   - `device_name`: Имя охранной системы, данное пользователем в Pandora Online
  #   - `type_name`: Название типа объекта ('Engine', 'Active Protection', и т.д.)
  #   - `type`: Внутренний идентификатор типа объекта (`engine`, `moving`, и т.д.)
  #
  name_format: '{device_name} {type_name}'
  ...
```

#### Дополнительная конфигурация подключения платформ:
Следующие примеры отражают возможные способы предварительной конфигурации добавляемых в Home Assistant объектов.
Ознакомиться со списком добавляемых объектов по-умолчанию (при первом запуске/добавлении конфигурации) Вы
можете в следующем разделе инструкции. Возможность предварительной конфигурации реализована для сохранения
портативности конфигурации при переносе её на другие платформы.
```yaml
  ...
  # В данном примере платформа `sensor` будет добавлена со всеми объектами:
  #
  sensor: True

  # В данном примере платформа `device_tracker` не будет добавлена:
  #
  device_tracker: False

  # В данном примере, для всех устройств в аккаунте будут включены только указанные
  # объекты платформы `binary_sensor`:
  #
  binary_sensor: ['moving', 'left_front_door']

  # В данном примере, устройства:
  # - '00000001' будет обладать переключателями `engine`, `tracking` и `coolant_heater`
  # - '00000002' будет обладать всеми переключателями
  # - '00000003' не будет иметь переключателей
  # - '00000004' (не указано ниже) будет обладать переключателями `active_security` и `engine`,
  #   так как данные переключатели установлены параметром `default` для устройств, не имеющих
  #   конкретизированную конфигурацию платформы
  #
  switch:
    default: ['active_security', 'engine']
    '00000001': ['engine', 'tracking', 'coolant_heater']
    '00000002': True
    '00000003': False
```

**N.B.** Настоятельно рекомендуется оборачивать идентификаторы устройств в кавычки во избежание конвертации
идентификаторов как числа, в некоторых случаях не соответствующие действительным идентификаторам.

**N.B.** Для платформы `device_tracker` отсутствует возможность конкретизации объектов в силу существования
единственного объекта; допускается включение/отключение платформы для конкретных устройств одним из способов,
указанных выше.

### Управление объектами через интерфейс
Дополнительно имеется возможость (для всех вариантов конфигурации) использовать раздел устройств для управления
включёнными объектами. Для этого:
1. Перейдите в раздел _Настройки_ &#10230; _Устройства_ (`/config/devices/dashboard`)
1. Найдите Ваше устройство (в колонке _Интеграция_ будет написано `Pandora Car Alarm System`)
1. Нажмите на найденную строку с устройством
1. Прокрутите страницу вниз до обнаружения надписи `+[N] скрытых объектов`
1. Нажмите на данную надпись
1. Нажмите на любой из появившихся объектов
1. Во всплывающем окне, переместите переключатель `Отображать объект` в положение `Вкл.`
1. Нажмите на кнопку `Обновить` в нижнем правом углу всплывающего окна

Пример того, как выглядит наполненная страница для устройства модели X-1911BT (нажмите для увеличения):

[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_1.png" alt="Карточка устройства X-1911BT, часть 1" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_1.png)
[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_2.png" alt="Карточка устройства X-1911BT, часть 2" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_2.png)
[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_3.png" alt="Карточка устройства X-1911BT, часть 3" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_3.png)

## Датчики / Переключатели / Состояния

Для привязки к автомобилю в имени объекта сенсоров используется идентификатор `PANDORA_ID`, в то время как в
человеко-читаемом названии используется название автомобиля с сайта Pandora. Это сделано для того, чтобы при
изменении названия автомобиля на сайте не менялись имена объектов, а значит не будет необходимости перенастраивать
lovelace UI и автоматизации.

> **ВНИМАНИЕ!**  
> При добавлении объектов, компонент в отдельных случаях проверяет поддержку функционала конечным устройством.
> Во избежание неожиданных ситуаций,  Вы можете ознакомиться с таблицами поддержки на официальном сайте Pandora:
> [ссылка на документ](https://alarmtrade.ru/service/sravnitelnye-tablitsy-sistem-pandora-i-pandect/).

### Платформа `sensor`
<a id="platform_sensor"/>

| Объект | Назначение | Примечание |
| ------ | ---------- | ---------- | 
| sensor.`PANDORA_ID`_mileage | Пробег | км |
| sensor.`PANDORA_ID`_fuel | Наполненность топливом <sup>1</sup> | % |
| sensor.`PANDORA_ID`_interior_temperature | Температура салона | °C |
| sensor.`PANDORA_ID`_engine_temperature | Температура двигателя | °C |
| sensor.`PANDORA_ID`_exterior_temperature | Уличная температура | °C |
| sensor.`PANDORA_ID`_balance | Баланс СИМ-карты <sup>2</sup> | ₽ |
| sensor.`PANDORA_ID`_speed | Скорость | км/ч |
| sensor.`PANDORA_ID`_tachometer | Тахометр (обороты двигателя) | rpm |
| sensor.`PANDORA_ID`_gsm_level | Уровень сигнала GSM| 0 ... 3 |
| sensor.`PANDORA_ID`_battery_voltage | Напряжение аккумулятора | В |
| sensor.`PANDORA_ID`_left_front_tire_pressure | Давление левой передней шины<sup>1</sup> | кПа |
| sensor.`PANDORA_ID`_right_front_tire_pressure | Давление правой передней шины<sup>1</sup> | кПа |
| sensor.`PANDORA_ID`_left_back_tire_pressure | Давление левой задней шины<sup>1</sup> | кПа |
| sensor.`PANDORA_ID`_right_back_tire_pressure | Давление правой задней шины<sup>1</sup> | кПа |

<sup>1</sup> Данные объекты будут доступны только в том случае, если Ваше устройство предоставляет
информацию о соответствующих им характеристиках по CAN-шине. Уточняйте поддержку у производителя.
 
<sup>1</sup> В грядущих релизах будет реализовано отображение топлива в литрах в качестве атрибутов данного датчика.  
<sup>2</sup> Будет изменено на реальную валюту СИМ-карты  

### Платформа `binary_sensor`
<a id="platform_binary_sensor"/>

| Объект | Назначение | Примечание |
| ------ | ---------- | ---------- |
| binary_sensor.`PANDORA_ID`_connection_state | Связь с автомобилем<sup>*</sup> | есть / нет |
| binary_sensor.`PANDORA_ID`_moving  | Статус движения | в движении / без движения |
| binary_sensor.`PANDORA_ID`_left_front_door | Левая передняя дверь | открыта / закрыта |
| binary_sensor.`PANDORA_ID`_right_front_door | Правая передняя дверь | открыта / закрыта |
| binary_sensor.`PANDORA_ID`_left_back_door | Левая задняя дверь | открыта / закрыта |
| binary_sensor.`PANDORA_ID`_right_back_door | Правая задняя дверь | открыта / закрыта |
| binary_sensor.`PANDORA_ID`_trunk | Багажник | открыт / закрыт |
| binary_sensor.`PANDORA_ID`_hood | Капот | открыт / закрыт |
| binary_sensor.`PANDORA_ID`_parking  | Режим паркнинга | включен / выключен |
| binary_sensor.`PANDORA_ID`_brakes  | Педаль тормоза | нажата / отпущена |
| binary_sensor.`PANDORA_ID`_left_front_glass | Левое переднее окно (водительское)<sup>1,2</sup> | открыто / закрыто |
| binary_sensor.`PANDORA_ID`_right_front_glass | Правое переднее окно (пассажирское)<sup>1,2</sup> | открыто / закрыто |
| binary_sensor.`PANDORA_ID`_left_back_glass | Левое заднее окно<sup>1</sup> | открыто / закрыто |
| binary_sensor.`PANDORA_ID`_right_back_glass | Правое заднее окно<sup>1</sup> | открыто / закрыто |

<sup>1</sup> Данные объекты будут доступны только в том случае, если Ваше устройство предоставляет
информацию о соответствующих им характеристиках по CAN-шине. Уточняйте поддержку у производителя.  
<sup>2</sup> Компонент не тестировался для праворульных транспортных средств. Может возникнуть
ситуация, что из коробки данные сенсоры перепутаны местами.

### Платформы `lock` и `switch`
<a id="platform_lock"/>
<a id="platform_switch"/>

> Внимание! Через 10с после изменения состояния переключателя производится принудительное автоматическое обновление 
> состояния автомобиля. Данный функционал вскоре будет возможно отключить вручную.

| Объект | Назначение | Примечание |
| ------ | ---------- | ---------- |
| lock.`PANDORA_ID`_central_lock | Статус блокировки замка | разблокирован / заблокирован |
| switch.`PANDORA_ID`_active_security | Статус активной защиты | включена / выключена |
| switch.`PANDORA_ID`_coolant_heater | Статус предпускового подогревателя | включен / выключен |
| switch.`PANDORA_ID`_engine | Статус двигателя | запущен / заглушен |
| switch.`PANDORA_ID`_tracking | Статус отслеживания (GPS-трек) | включен / выключен |
| switch.`PANDORA_ID`_service_mode | Режим сервиса (обслуживания) | включен / выключен |
| switch.`PANDORA_ID`_ext_channel | Дополнительный канал <sup>3</sup> | включить / выключить |
 
<sup>3</sup> Состояние не остслеживается  

### Платформа `device_tracker`
<a id="platform_device_tracker"/>

Для каждого автомобиля будет создан объект device_tracker.pandora_`PANDORA_ID`, где `PANDORA_ID` уникальный идентификатор автомобиля в системе Pandora. Доступны все обычные действия для Device Tracker: отслеживание местоположения [на карте](https://www.home-assistant.io/lovelace/map/), [треккинг пути](https://www.home-assistant.io/blog/2020/04/08/release-108/#lovelace-map-history), [контроль зон](https://www.home-assistant.io/docs/automation/trigger/#zone-trigger) и т.д.

## Команды / Службы
<a id="services_provided"/>

Ключевые команды включения/выключения определённых функций вынесены в отдельные переключаемые объекты
(пр. `switch` и `lock`). Если же имеется потребность выступить за рамки предопределённых конфигураций,
существуют два способа передать дополнительные команды на охранную систему.

Для _именованого_ способа требуется вызов службы в формате `pandora_cas.<Постфикс>`:
```yaml
# Именованый способ вызова команд
- action: call-service
  service: pandora_cas.start_engine
  service_data:
    device_id: 1231234123
```

Для _универсального_ способа идентификаторы команд (`command_id`) обязательно должны быть числовыми:
```yaml
# Универсальный способ вызова команд
- action: call-service
  service: pandora_cas.remote_command
  service_data:
    device_id: 1234141243
    command_id: 1
```

Для справки, ниже представлена таблица доступных к выполнению команд (сгруппированых по смысловому признаку):

| ID      | Постфикс | Действие | Примечание |
| ------- | -------- | -------- | ---------- |
| **1**   | `lock` | Поставить на охрану | Может быть запрещено настройками блока сигнализации |
| **2**   | `unlock` | Снять с охраны | Может быть запрещено настройками блока сигнализации |
| **4**   | `start_engine` | Запустить двигатель | |
| **8**   | `stop_engine` | Остановить двигатель | |
| **16**  | `enable_tracking` | Включить GPS-трекинг | Поддерживается не всеми устройствами  |
| **32**  | `disable_tracking` | Выключить GPS-трекинг | Поддерживается не всеми устройствами  |
| **17**  | `enable_active_security` | Включить активную безопасность | Поддерживается не всеми устройствами |
| **18**  | `disable_active_security` | Выключить активную безопасность | Поддерживается не всеми устройствами |
| **21**  | `turn_on_coolant_heater` | Включить преднагреватель | Поддерживается не всеми устройствами |
| **22**  | `turn_off_coolant_heater` | Выключить преднагреватель | Поддерживается не всеми устройствами |
| **33**  | `turn_on_ext_channel` | Включить дополнительный канал | Поддерживается не всеми устройствами |
| **34**  | `turn_off_ext_channel` | Выключить дополнительный канал | Поддерживается не всеми устройствами |
| **40**  | `enable_service_mode` | Включить сервисный режим | |
| **41**  | `disable_service_mode` | Выключить сервисный режим | |
| **23**  | `trigger_horn` | Издать сигнал клаксона | |
| **24**  | `trigger_light` | Включить освещение | |
| **255** | `check` | Команда CHECK | ? |
| **100** | `additional_command_1` | Дополнительная команда №1 | Настраивается инструментами конфигурации блока сигнализации |
| **128** | `additional_command_2` | Дополнительная команда №2 | Настраивается инструментами конфигурации блока сигнализации |
| **240** | `enable_connection` | Продлить период коммуникации | ? |
| **15**  | `disable_connection` | Завершить период коммуникации | ? |

### Примеры использования команд
<a id="service_examples"/>

Вкладка с кнопкой запуска двигателя

```yaml
  - badges: []
    cards:
      - hold_action:
          action: call-service
          service: pandora_cas.start_engine
          service_data:
            id: 1234567890
        icon: 'mdi:fan'
        name: Запуск двигателя
        show_icon: true
        show_name: true
        tap_action:
          action: more-info
        type: button
    icon: 'mdi:car'
    panel: false
    path: honda_pilot
    title: Honda Pilot
```

Автоматизация включения доп. канала по событию с условиями. Подробнее см. [пример использования](https://www.drive2.ru/l/526540176697066100/).

```yaml
# Фрагмент файла automations.yaml
- id: switch_on_pilot_seat_heaters
  alias: Включить подогрев сидений
  trigger:
    platform: state
    entity_id: binary_sensor.1234567890_engine_state
    to: 'on'
  condition:
  - condition: time
    after: 05:58:00
    before: 06:12:00
    weekday:
    - mon
    - tue
    - wed
    - thu
    - fri
  action:
    service: pandora_cas.turn_on_ext_channel
    data_template:
      id: 1234567890
```

## Отказ от ответственности

Данное программное обеспечение никак не связано и не одобрено ООО «НПО Телеметрия», владельца торговой марки Pandora. Используйте его на свой страх и риск. Автор ни при каких обстоятельствах не несет ответственности за порчу или утрату вашего имущества и возможного вреда в отношении третьих лиц.

Все названия брендов и продуктов принадлежат их законным владельцам.
