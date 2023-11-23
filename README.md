<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/header.png" height="100" alt="Home Assistant + Pandora">

# _Pandora Car Alarm System_ для _Home Assistant_

> Автоматизация управления охранными системами Pandora™ и PanDECT<sup>®</sup> в
> Home Assistant.
>
> [![hacs_badge](https://img.shields.io/badge/HACS-Default-green.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
> [![Лицензия](https://img.shields.io/badge/%D0%9B%D0%B8%D1%86%D0%B5%D0%BD%D0%B7%D0%B8%D1%8F-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
> [![Поддержка](https://img.shields.io/badge/%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%B8%D0%B2%D0%B0%D0%B5%D1%82%D1%81%D1%8F%3F-%D0%B4%D0%B0-green.svg?style=for-the-badge)](https://github.com/alryaz/hass-pandora-cas/graphs/commit-activity)

> 💵 **Пожертвование на развитие проекта**  
> [![Пожертвование YooMoney](https://img.shields.io/badge/YooMoney-8B3FFD.svg?style=for-the-badge)](https://yoomoney.ru/to/410012369233217)
> [![Пожертвование Тинькофф](https://img.shields.io/badge/Tinkoff-F8D81C.svg?style=for-the-badge)](https://www.tinkoff.ru/cf/3g8f1RTkf5G)
> [![Пожертвование Cбербанк](https://img.shields.io/badge/Сбербанк-green.svg?style=for-the-badge)](https://www.sberbank.com/ru/person/dl/jc?linkname=3pDgknI7FY3z7tJnN)
> [![Пожертвование DonationAlerts](https://img.shields.io/badge/DonationAlerts-fbaf2b.svg?style=for-the-badge)](https://www.donationalerts.com/r/alryaz)
>
> 💬 **Техническая поддержка**  
> [![Группа в Telegram](https://img.shields.io/endpoint?url=https%3A%2F%2Ftg.sumanjay.workers.dev%2Falryaz_ha_addons&style=for-the-badge)](https://telegram.dog/alryaz_ha_addons)
>
> 🥇 **Вдохновитель, оригинальный разработчик**  
> [![Репозиторий GitHub](https://img.shields.io/badge/GitHub-turbulator%2Fpandora--cas-blue?style=for-the-badge)](https://github.com/turbulator/pandora-cas)

Автомобиль тоже может быть частью умного дома. С помощью этого компонента вы
сможете отслеживать состояние, управлять и автоматизировать свой автомобиль,
если он оборудован охранной системой Pandora. После настройки ваши устройства
Pandora™ и PanDECT<sup>®</sup> автоматически добавятся в _Home Assistant_.

Компонент реализует доступ к API официального приложения Pandora, _Pandora
Connect_, и реализует часть его функционала. Для настройки Вам следует использовать те же авторизационные данные, что вы
используете на сайте Pandora ([pro.p-on.ru](https://pro.p-on.ru)), или в
мобильном приложении
[Pandora Online / Connect / Pro](https://play.google.com/store/apps/details?id=ru.alarmtrade.pandora&hl=ru).

На данный момент компонент поддерживает:

- [Device Tracker](#platform_device_tracker): Местоположение автомобиля.
- [Sensors](#platform_sensor): Температура, скорость, тахометр и т.д.
- [Binary Sensors](#platform_binary_sensor): Статусы открытия, движения, и т.д.
- [Switches](#platform_switch): Работа двигателя, активная охрана, и т.д.
- [Lock](#platform_lock): Постановка на охрану
- [Services](#services_provided): Команды, например: открыть/закрыть,
  завести/заглушить и др.

Компонент успешно протестирован и отработан на системах:

- PanDECT X-1700 BT
- PanDECT X-1900 BT
- Pandora DX-4G
- Pandora DX-90BT + NAV-10
- Pandora DX-9X LoRa + NAV-10
- Pandora DXL-4970
- Pandora DXL-5570
- Pandora NAV-08 _(маячок)_
- Pandora VX-4G GPS
- _[Сообщите о Вашем успехе!](mailto:alryaz@alryaz.com?subject=Pandora%20Car%20Alarm%20System%20%D0%B4%D0%BB%D1%8F%20Home%20Assistant%20-%20%D0%9F%D0%BE%D0%B4%D0%B4%D0%B5%D1%80%D0%B6%D0%BA%D0%B0%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%B0&body=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5!%0D%0A%0D%0A%D0%9F%D0%BE%D0%B4%D1%82%D0%B2%D0%B5%D1%80%D0%B6%D0%B4%D0%B0%D1%8E%2C%20%D1%87%D1%82%D0%BE%20%D0%B8%D0%BD%D1%82%D0%B5%D0%B3%D1%80%D0%B0%D1%86%D0%B8%D1%8F%20%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%B0%D0%B5%D1%82%20%D1%81%20%D0%BC%D0%BE%D0%B8%D0%BC%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%BE%D0%BC%20...!%0D%0A%0D%0A(%D0%95%D1%81%D0%BB%D0%B8%20%D1%8D%D1%82%D0%BE%20%D0%BD%D0%B5%20%D1%82%D0%B0%D0%BA%2C%20%D0%BE%D0%BF%D0%B8%D1%88%D0%B8%D1%82%D0%B5%2C%20%D0%BF%D0%BE%D0%B6%D0%B0%D0%BB%D1%83%D0%B9%D1%81%D1%82%D0%B0%2C%20%D0%92%D0%B0%D1%88%D0%B8%20%D0%BD%D0%B0%D0%B1%D0%BB%D1%8E%D0%B4%D0%B5%D0%BD%D0%B8%D1%8F%20%D0%BE%20%D0%BD%D0%B5%D0%BF%D0%BE%D0%BB%D0%B0%D0%B4%D0%BA%D0%B0%D1%85))_

## Скриншоты

<details>
    <summary>Панель со всеми поддерживаемыми элементами</summary> 
    <img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_default.png" alt="Скриншот: Панель со всеми поддерживаемыми элементами">
</details>
<details>
    <summary>Карточка устройства (тёмная тема)</summary> 
    <img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/stack_default_dark.png" alt="Скриншот: Карточка устройства (тёмная тема)">
</details>
<details>
    <summary>Доступные виды курсоров трекера</summary>
    <ul>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/arrow.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/arrow.svg" width="32" height="32" alt="Курсор: arrow"></a> &mdash; <em>arrow</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/bird.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/bird.svg" width="32" height="32" alt="Курсор: bird"></a> &mdash; <em>bird</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/car.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/car.svg" width="32" height="32" alt="Курсор: car"></a> &mdash; <em>car</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/helicopter.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/helicopter.svg" width="32" height="32" alt="Курсор: helicopter"></a> &mdash; <em>helicopter</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/moto.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/moto.svg" width="32" height="32" alt="Курсор: moto"></a> &mdash; <em>moto</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/pierced_heart.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/pierced_heart.svg" width="32" height="32" alt="Курсор: pierced_heart"></a> &mdash; <em>pierced_heart</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/plane.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/plane.svg" width="32" height="32" alt="Курсор: plane"></a> &mdash; <em>plane</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/quadrocopter.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/quadrocopter.svg" width="32" height="32" alt="Курсор: quadrocopter"></a> &mdash; <em>quadrocopter</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/rocket.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/rocket.svg" width="32" height="32" alt="Курсор: rocket"></a> &mdash; <em>rocket</em></li>
        <li><a href="https://github.com/alryaz/hass-pandora-cas/blob/master/custom_components/pandora_cas/cursors/truck.svg" target="_blank"><img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/custom_components/pandora_cas/cursors/truck.svg" width="32" height="32" alt="Курсор: truck"></a> &mdash; <em>truck</em></li>
    </ul>
</details>

## Установка

### Home Assistant Community Store

> 🎉  **Рекомендованный метод установки.**

[![Открыть Ваш Home Assistant и открыть репозиторий внутри Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alryaz&repository=hass-pandora-cas&category=integration)

1. Установите HACS ([инструкция по установке на оф. сайте](https://hacs.xyz/docs/installation/installation/)).
2. Добавьте репозиторий в список дополнительных:
    1. Откройте главную страницу _HACS_.
    2. Откройте раздел _Интеграции (Integrations)_.
    3. Нажмите три точки сверху справа (допонительное меню).
    4. Выберите _Пользовательские репозитории_.
    5. Скопируйте `https://github.com/alryaz/hass-pandora-cas` в поле ввода
    6. Выберите _Интеграция (Integration)_ в выпадающем списке.
    7. Нажмите _Добавить (Add)_.
3. Найдите `Pandora Car Alarm System` в поиске по интеграциям.
4. Установите последнюю версию компонента, нажав на кнопку `Установить` (`Install`).
5. Перезапустите сервер _Home Assistant_.

### Вручную

> ⚠️ **Внимание!** Данный вариант **<ins>не рекомендуется</ins>** в силу
> сложности поддержки установленной интеграции в актуальном состоянии.

1. Скачайте [архив с актуальной стабильной версией интеграции](https://github.com/alryaz/hass-pandora-cas/releases/latest/download/pandora_cas.zip)
2. Создайте папку (если не существует) `custom_components` внутри папки с конфигурацией Home Assistant
3. Создайте папку `pandora_cas` внутри папки `custom_components`
4. Извлеките содержимое скачанного архива в папку `pandora_cas`
5. Перезапустите сервер _Home Assistant_

## Настройка

### Через интерфейс _"Интеграции"_

Поддерживается базовый функционал конфигурации через веб-интерфейс _Home
Assistant_. Конфигурация данным способов
возможна без перезагрузки _Home Assistant_.

[![Установить интеграцию pandora_cas](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=pandora_cas)

<details>
  <summary>Вручную (если кнопка выше не работает)</summary>
  Для перехода к настройке, выполните следующие действия:
  <ol>
    <li>Перейдите в раздел <i>Настройки</i>&nbsp;&#10230;&nbsp;<i>Интеграции</i> (`/config/integrations`)</li>
    <li>Нажмите на круглую кнопку с плюсом внутри в нижнем правом углу экрана</li>
    <li>Во всплывшем окне, введите в верхнем поле поиска: <b>Pandora</b>; одним из результатов должен оказаться <b>Pandora&nbsp;Car&nbsp;Alarm&nbsp;System</b> (с соответствующим логотипом торговой марки <i>Pandora Car Alarm System</i>)</li>
    <li>Нажмите на предложенный результат</li>
    <li>Введите имя пользователя и пароль в соответствующие поля</li>
    <li>Нажмите внизу справа на кнопку <i>Подтвердить</i>. В случае обнаружения системой каких-либо ошибок, они будут отображены в окошке</li>
    <li>Обновление займёт не более 5-10 секунд (проверено на Raspberry Pi 4), элементы в конфигурации по-умолчанию должны появиться на главном экране (при использовании конфигурациии Lovelace по-умолчанию)</li>
  </ol>
</details>

### Посредством YAML

> ⚠️ **Внимание!** Данный вариант **<ins>не рекомендуется</ins>** в силу
> сложности поддержки установленной интеграции в актуальном состоянии.

Чтобы активировать компонент, добавьте эти строки в файл `configuration.yaml`:

```yaml
# Фрагмент файла configuration.yaml
pandora_cas:
  # Учётная запись на портале p-on.ru / pro.p-on.ru
  password: !secret YOUR_PASSWORD  # обязательно
  username: !secret YOUR_USERNAME  # обязательно
```

Компонент также поддерживает работу с несколькими учётными записями:

```yaml
pandora_cas:
  # Первая учётная запись
  - username: !secret YOUR_USERNAME_1
    password: !secret YOUR_PASSWORD_1

    # Вторая учётная запись
  - username: !secret YOUR_USERNAME_2
    password: !secret YOUR_PASSWORD_2
```

### Управление объектами через интерфейс

<a id="integration_entities_control"></a>

Дополнительно имеется возможость (для всех вариантов конфигурации) использовать
раздел устройств для управления
включёнными объектами. Для этого:

1. Перейдите в раздел _Настройки_ &#10230;
   _Устройства_ (`/config/devices/dashboard`)
2. Найдите Ваше устройство (в колонке
   _Интеграция_ будет написано `Pandora Car Alarm System`)
3. Нажмите на найденную строку с устройством
4. Прокрутите страницу вниз до обнаружения надписи `+[N] скрытых объектов`
5. Нажмите на данную надпись
6. Нажмите на любой из появившихся объектов
7. Во всплывающем окне, переместите переключатель `Отображать объект` в положение `Вкл.`
8. Нажмите на кнопку `Обновить` в нижнем правом углу всплывающего окна

Пример того, как выглядит наполненная страница для устройства модели X-1911BT (нажмите для увеличения):

[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_1.png" alt="Карточка устройства X-1911BT, часть 1" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_1.png)
[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_2.png" alt="Карточка устройства X-1911BT, часть 2" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_2.png)
[<img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_device_card_3.png" alt="Карточка устройства X-1911BT, часть 3" width="31%">](https://github.com/alryaz/hass-pandora-cas/blob/master/images/screenshot_device_card_3.png)

## Датчики / Переключатели / Состояния

Для привязки к автомобилю в имени объекта сенсоров используется
идентификатор `PANDORA_ID`, в то время как в
человеко-читаемом названии используется название автомобиля с сайта Pandora. Это
сделано для того, чтобы при
изменении названия автомобиля на сайте не менялись имена объектов, а значит не
будет необходимости перенастраивать
lovelace UI и автоматизации.

> **ВНИМАНИЕ!**  
> При добавлении объектов, компонент в отдельных случаях проверяет поддержку
> функционала конечным устройством.
> Во избежание неожиданных ситуаций, Вы можете ознакомиться с таблицами
> поддержки на официальном сайте Pandora:
> [ссылка на документ](https://alarmtrade.ru/service/sravnitelnye-tablitsy-sistem-pandora-i-pandect/).

> **ПРЕДУПРЕЖДЕНИЕ!**  
> Общее количество различных объектов, доступных в компоненте, в скором времени
> перевалит за 40.
> Ввиду этого, по умолчанию отключены объекты, встречающиеся наиболее редко,
> такие как:
> - Состояние зарядки и температура аккумулятора гибридных/электрических
    автомобилей
> - Состояние поднятости стёкол и давление в шинах (TPMS), получаемые по
    CAN-шине
>
> Такие объекты помечаются символом "&#9888;" в таблицах ниже. Если Вы уверены,
> что Ваш автомобиль
> вкупе с установленной на нём системой поддерживают данные функции, то Вы
> можете включить
> перечисленные объекты следуя инструкции [выше](#integration_entities_control).

### Платформа `sensor`

<a id="platform_sensor"></a>

| Объект                                                     | Назначение                             | Примечание     |
|------------------------------------------------------------|----------------------------------------|----------------|
| sensor.`PANDORA_ID`_mileage                                | Пробег сигнализации (по GPS)           | км             |
| sensor.`PANDORA_ID`_can_mileage                            | Пробег штатного одометра (по шине CAN) | км             |
| sensor.`PANDORA_ID`_fuel                                   | Наполненность топливом <sup>1</sup>    | %              |
| sensor.`PANDORA_ID`_interior_temperature                   | Температура салона                     | °C             |
| sensor.`PANDORA_ID`_engine_temperature                     | Температура двигателя                  | °C             |
| sensor.`PANDORA_ID`_exterior_temperature                   | Уличная температура                    | °C             |
| sensor.`PANDORA_ID`_battery_temperature                    | Температура аккумулятора               | °C             |
| sensor.`PANDORA_ID`_balance                                | Баланс СИМ-карты                       | Валюта баланса |
| sensor.`PANDORA_ID`_speed                                  | Скорость                               | км/ч           |
| sensor.`PANDORA_ID`_tachometer                             | Тахометр (обороты двигателя)           | rpm            |
| sensor.`PANDORA_ID`_gsm_level                              | Уровень сигнала GSM                    | 0 ... 3        |
| sensor.`PANDORA_ID`_battery_voltage                        | Напряжение аккумулятора                | V              |
| sensor.`PANDORA_ID`_last_online                            | Последний выход на связь               | Метка времени  |
| sensor.`PANDORA_ID`_last_state_update                      | Последнее получение обновления         | Метка времени  |
| sensor.`PANDORA_ID`_last_settings_change                   | Последнее изменение настроек системы   | Метка времени  |
| sensor.`PANDORA_ID`_last_command_execution                 | Последнее выполнение команды           | Метка времени  |
| &#9888;&nbsp;sensor.`PANDORA_ID`_balance_secondary         | _Баланс дополнительной СИМ-карты_      | Валюта баланса |
| &#9888;&nbsp;sensor.`PANDORA_ID`_can_mileage_to_empty      | _Пробег до пустого бака (по шине CAN)_ | км             |
| &#9888;&nbsp;sensor.`PANDORA_ID`_left_front_tire_pressure  | _Давление левой передней шины_         | кПа _(?)_      |
| &#9888;&nbsp;sensor.`PANDORA_ID`_right_front_tire_pressure | _Давление правой передней шины_        | кПа _(?)_      |
| &#9888;&nbsp;sensor.`PANDORA_ID`_left_back_tire_pressure   | _Давление левой задней шины_           | кПа _(?)_      |
| &#9888;&nbsp;sensor.`PANDORA_ID`_right_back_tire_pressure  | _Давление правой задней шины_          | кПа _(?)_      |
| &#9888;&nbsp;sensor.`PANDORA_ID`_reserve_tire_pressure     | _Давление правой задней шины_          | кПа _(?)_      |

### Платформа `binary_sensor`

<a id="platform_binary_sensor"></a>

| Объект                                                        | Назначение                                        | Примечание                |
|---------------------------------------------------------------|---------------------------------------------------|---------------------------|
| binary_sensor.`PANDORA_ID`_connection_state                   | Связь с автомобилем<sup>1</sup>                   | есть / нет                |
| binary_sensor.`PANDORA_ID`_moving                             | Статус движения                                   | в движении / без движения |
| binary_sensor.`PANDORA_ID`_left_front_door                    | Левая передняя дверь                              | открыта / закрыта         |
| binary_sensor.`PANDORA_ID`_right_front_door                   | Правая передняя дверь                             | открыта / закрыта         |
| binary_sensor.`PANDORA_ID`_left_back_door                     | Левая задняя дверь                                | открыта / закрыта         |
| binary_sensor.`PANDORA_ID`_right_back_door                    | Правая задняя дверь                               | открыта / закрыта         |
| binary_sensor.`PANDORA_ID`_trunk                              | Багажник                                          | открыт / закрыт           |
| binary_sensor.`PANDORA_ID`_hood                               | Капот                                             | открыт / закрыт           |
| binary_sensor.`PANDORA_ID`_parking                            | Режим паркнинга                                   | включен / выключен        |
| binary_sensor.`PANDORA_ID`_brakes                             | Педаль тормоза                                    | нажата / отпущена         |
| &#9888;&nbsp;binary_sensor.`PANDORA_ID`_left_front_glass      | _Левое переднее окно (водительское)<sup>2</sup>_  | открыто / закрыто         |
| &#9888;&nbsp;binary_sensor.`PANDORA_ID`_right_front_glass     | _Правое переднее окно (пассажирское)<sup>2</sup>_ | открыто / закрыто         |
| &#9888;&nbsp;binary_sensor.`PANDORA_ID`_left_back_glass       | _Левое заднее окно_                               | открыто / закрыто         |
| &#9888;&nbsp;binary_sensor.`PANDORA_ID`_right_back_glass      | _Правое заднее окно_                              | открыто / закрыто         |
| &#9888;&nbsp;binary_sensor.`PANDORA_ID`_ev_charging_connected | _Зарядка аккумулятора электрокара_                | подключено / отключено    |

<sup>1</sup> Данный объект содержит полный перечень свойств, получаемых в момент
обновления состояния автомобиля,
и тем самым может быть запросто использован для `template`-выражений.  
<sup>2</sup> Компонент не тестировался для праворульных транспортных средств.
Может возникнуть
ситуация, что из коробки данные сенсоры перепутаны местами.

### Платформы `lock` и `switch`

<a id="platform_lock"></a>
<a id="platform_switch"></a>

| Объект                              | Назначение                                     | Примечание                   |
|-------------------------------------|------------------------------------------------|------------------------------|
| lock.`PANDORA_ID`_central_lock      | Статус блокировки замка                        | разблокирован / заблокирован |
| switch.`PANDORA_ID`_active_security | Статус активной защиты                         | включена / выключена         |
| switch.`PANDORA_ID`_coolant_heater  | Статус предпускового подогревателя             | включен / выключен           |
| switch.`PANDORA_ID`_engine          | Статус двигателя                               | запущен / заглушен           |
| switch.`PANDORA_ID`_tracking        | Статус отслеживания (GPS-трек)                 | включен / выключен           |
| switch.`PANDORA_ID`_service_mode    | Режим сервиса (обслуживания)                   | включен / выключен           |
| switch.`PANDORA_ID`_ext_channel     | Дополнительный канал <sup>3</sup>              | включить / выключить         |
| switch.`PANDORA_ID`_status_output   | Статусный выход (для нештатных иммобилайзеров) | включить / выключить         |

<sup>3</sup> Состояние не остслеживается

### Платформа `button`

<a id="platform_button"></a>

| Объект                                   | Назначение                        | Примечание |
|------------------------------------------|-----------------------------------|------------|
| switch.`PANDORA_ID`_erase_errors         | Очистка кодов ошибок              |            |
| switch.`PANDORA_ID`_read_errors          | Считывание кодов ошибок           |            |
| switch.`PANDORA_ID`_trigger_horn         | Статус двигателя                  |            |
| switch.`PANDORA_ID`_trigger_light        | Статус отслеживания (GPS-трек)    |            |
| switch.`PANDORA_ID`_trigger_trunk        | Режим сервиса (обслуживания)      |            |
| switch.`PANDORA_ID`_check                | Дополнительный канал <sup>3</sup> |            |
| switch.`PANDORA_ID`_additional_command_1 | Дополнительная команда №1         |            |
| switch.`PANDORA_ID`_additional_command_2 | Дополнительная команда №2         |            |

### Платформа `device_tracker`

<a id="platform_device_tracker"></a>

Для каждого автомобиля будет создан объект device_tracker.pandora_`PANDORA_ID`,
где
`PANDORA_ID` уникальный идентификатор автомобиля в системе Pandora. Доступны все
обычные действия для Device Tracker: отслеживание местоположения
[на карте](https://www.home-assistant.io/lovelace/map/),
[трекинг пути](https://www.home-assistant.io/blog/2020/04/08/release-108/#lovelace-map-history),
[контроль зон](https://www.home-assistant.io/docs/automation/trigger/#zone-trigger)
и т.д.

<details>
  <summary>Пример отображения маркера на карте (цвет, поворот)</summary>
  <img src="https://raw.githubusercontent.com/alryaz/hass-pandora-cas/master/images/screenshot_map_marker.png" alt="Скриншот: Маркер автомобиля с поворотом на карте Home Assistant">
</details>

Объект обладает следующими атрибутами:

| Параметр  |   Тип   | Описание                       |
|-----------|:-------:|--------------------------------|
| latitude  | `float` | Широта                         |
| longitude | `float` | Долгота                        |
| device_id |  `int`  | Идентификатор устройства       |
| direction |  `int`  | Направление (в градусах)       |
| cardinal  |  `str`  | Направление (в сторонах света) |

## События

<a id="events_supported"></a>

За период наблюдения компонентом за автомобилем могут происходить некоторые
события, чьи
свойства не позволяют сделать из них удобные к использованию объекты
платформ `sensor`,
`binary_sensor` и пр. Ввиду этого, для поддержки дополнительных событий введены
два новых
внутренних делегата:

### Делегат событий `pandora_cas_event`

Данное событие делегирует информацию из системы Pandora прямиком в Home
Assistant. Следующие данные
будут доступны при получении события:

| Параметр             |   Тип   | Описание                 |
|----------------------|:-------:|--------------------------|
| device_id            |  `int`  | Идентификатор устройства |
| event_id_primary     |  `int`  | Первичный код события    |
| event_id_secondary   |  `int`  | Вторичный код события    |
| title_primary        | `str`, `None` | Заглавное наименование события |
| title_primary        | `str`, `None` | Уточняющее наименование события |
| event_type           |  `str`  | Код типа события         |
| latitude             | `float` | Широта                   | 
| longitude            | `float` | Долгота                  |
| gsm_level            |  `int`  | Уровень связи            |
| fuel                 |  `int`  | Уровень топлива          |
| exterior_temperature |  `int`  | Температура за бортом    |
| engine_temperature   |  `int`  | Температура двигателя    |

Код типа события является строкой, которая поверхностно описывает смысл события
(на английском языке). Полным списком кодов (кодификатором) возможно обзавестись
в файле
`api.py` проекта.

### Делегат событий `pandora_cas_command`

Для всех команд будут выполняться события-уведомители. Данные события содержат
следующие данные:

| Параметр   |  Тип  | Описание                                                           |
|------------|:-----:|--------------------------------------------------------------------|
| device_id  | `int` | Идентификатор устройства                                           |
| command_id | `int` | Номер команды _(см. раздел ниже)_                                  |
| result     | `int` | Результат выполнения (`0` - успех, любое другое значение - ошибка) |
| reply      | `int` | Код описания ошибки (больше нуля, если код доступен)               |

## Команды / Службы

<a id="services_provided"></a>

Ключевые команды включения/выключения определённых функций вынесены в отдельные
переключаемые объекты
(пр. `switch` и `lock`). Если же имеется потребность выступить за рамки
предопределённых конфигураций,
существуют два способа передать дополнительные команды на охранную систему.

Для _именованого_ способа требуется вызов службы в
формате `pandora_cas.<Постфикс>`:

```yaml
# Именованый способ вызова команд
- action: call-service
  service: pandora_cas.start_engine
  data:
    device_id: 1231234123
```

Для _универсального_ способа идентификаторы команд (`command_id`) обязательно
должны быть числовыми:

```yaml
# Универсальный способ вызова команд
- action: call-service
  service: pandora_cas.remote_command
  data:
    device_id: 1234141243
    command_id: 1
```

Для справки, ниже представлена таблица доступных к выполнению команд (
сгруппированых по смысловому признаку):

|      ID | Постфикс                  | Действие                        | Примечание                                                  |
|--------:|---------------------------|---------------------------------|-------------------------------------------------------------|
|   **1** | `lock`                    | Поставить на охрану             | Может быть запрещено настройками блока сигнализации         |
|   **2** | `unlock`                  | Снять с охраны                  | Может быть запрещено настройками блока сигнализации         |
|   **4** | `start_engine`            | Запустить двигатель             |                                                             |
|   **8** | `stop_engine`             | Остановить двигатель            |                                                             |
|  **16** | `enable_tracking`         | Включить GPS-трекинг            | Поддерживается не всеми устройствами                        |
|  **32** | `disable_tracking`        | Выключить GPS-трекинг           | Поддерживается не всеми устройствами                        |
|  **17** | `enable_active_security`  | Включить активную безопасность  | Поддерживается не всеми устройствами                        |
|  **18** | `disable_active_security` | Выключить активную безопасность | Поддерживается не всеми устройствами                        |
|  **21** | `turn_on_coolant_heater`  | Включить преднагреватель        | Поддерживается не всеми устройствами                        |
|  **22** | `turn_off_coolant_heater` | Выключить преднагреватель       | Поддерживается не всеми устройствами                        |
|  **33** | `turn_on_ext_channel`     | Включить дополнительный канал   | Поддерживается не всеми устройствами                        |
|  **34** | `turn_off_ext_channel`    | Выключить дополнительный канал  | Поддерживается не всеми устройствами                        |
|  **40** | `enable_service_mode`     | Включить сервисный режим        |                                                             |
|  **41** | `disable_service_mode`    | Выключить сервисный режим       |                                                             |
|  **23** | `trigger_horn`            | Издать сигнал клаксона          |                                                             |
|  **24** | `trigger_light`           | Включить освещение              |                                                             |
| **255** | `check`                   | Команда CHECK                   | ?                                                           |
| **100** | `additional_command_1`    | Дополнительная команда №1       | Настраивается инструментами конфигурации блока сигнализации |
| **128** | `additional_command_2`    | Дополнительная команда №2       | Настраивается инструментами конфигурации блока сигнализации |
| **240** | `enable_connection`       | Продлить период коммуникации    | ?                                                           |
|  **15** | `disable_connection`      | Завершить период коммуникации   | ?                                                           |
|  **48** | `enable_status_output`    | Выключение статусного выхода    | Подразумевается поддержка на стороне автомобиля             |
|  **49** | `disable_status_output`   | Включение статусного выхода     | Подразумевается поддержка на стороне автомобиля             |

### Примеры использования команд

<a id="service_examples"></a>

Вкладка с кнопкой запуска двигателя

```yaml
  - badges: [ ]
    cards:
      - hold_action:
          action: call-service
          service: pandora_cas.start_engine
          data:
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

Автоматизация включения доп. канала по событию с условиями. Подробнее
см. [пример использования](https://www.drive2.ru/l/526540176697066100/).

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

## Создание карточки устройства

Конфигурация существует трёх видов:

- [Карточка](https://github.com/alryaz/hass-pandora-cas/tree/master/interface/cards) (
  содержит только графическое изображение транспортного средства)
- [Стек](https://github.com/alryaz/hass-pandora-cas/tree/master/interface/stacks) (
  карточка + элементы управления + сенсоры)
- [Панель](https://github.com/alryaz/hass-pandora-cas/tree/master/interface/dashboards) (
  карта по левую сторону, стек по правую)

Чтобы подготовить собственную конфигурацию, выполните следующие действия:

1. Открыть [папку с подготовленными конфигурациями](https://github.com/alryaz/hass-pandora-cas/tree/master/interface)
2. Выбрать файл с желаемым типом конфигурации
3. Скопировать содержимое файла в текстовый редактор
4. Заменить все вхождения `REPLACE_WITH_PANDORA_ID` на идентификатор
   автомобиля (`device_id` на сенсорах)

## Отказ от ответственности

Данное программное обеспечение никак не связано и не одобрено ООО «НПО
Телеметрия», владельца торговой марки Pandora. Используйте его на свой страх и
риск. Автор ни при каких обстоятельствах не несет ответственности за порчу или
утрату вашего имущества и возможного вреда в отношении третьих лиц.

Все названия брендов и продуктов принадлежат их законным владельцам.
