#!/usr/bin/env python3
import argparse
import os
import tempfile
from base64 import b64encode
from io import BytesIO
from typing import Any, Iterator, Mapping, Union

import PIL.ImageChops
import attr
import requests
from PIL import Image


class NotSet(object): ...


NOT_SET = NotSet()
BASE_PATH = os.path.dirname(__file__)

_BASE_STYLE = {
    "transform": "none",
    "top": "0%",
    "left": "0%",
    "width": "100%",
    "height": "100%",
    "filter": "none",
}

SAVE_FORMAT = "webp"


class ForProcessing:
    def __init__(self, *, base_style: Mapping[str, Any] | None = None) -> None:
        self._base_style = _BASE_STYLE
        if base_style:
            self._base_style.update(base_style)

    @classmethod
    def image_as_data_uri(cls, image: Union[bytes, BytesIO, Image.Image]) -> str:
        if isinstance(image, Image.Image):
            buffered = BytesIO()
            image.save(buffered, format=SAVE_FORMAT)
            image = buffered

        if isinstance(image, BytesIO):
            image = image.getvalue()

        elif not isinstance(image, bytes):
            raise TypeError("must be either PIL.Image.Image or bytes")

        return f"data:image/{SAVE_FORMAT};base64,{b64encode(image).decode('ascii')}"

    @classmethod
    def make_image_dict(
        cls, image: Union[bytes, BytesIO, Image.Image], **kwargs
    ) -> dict[str, Any]:
        return {
            "type": "image",
            "image": cls.image_as_data_uri(image),
            **kwargs,
        }

    def get_style(self, style: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return (
            dict(self._base_style) if style is None else {**self._base_style, **style}
        )

    def _merge_style_kwarg(
        self, kwargs: dict[str, Any], style: Mapping[str, Any] | None = None
    ) -> None:
        final_styles = {}
        final_styles.update(self._base_style)
        final_styles.update(kwargs.pop("style", None) or {})
        final_styles.update(style or {})
        if final_styles:
            kwargs["style"] = final_styles

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> dict[str, Any]:
        raise NotImplementedError


class ForSimple(ForProcessing):
    def __init__(self, image_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.image_name = image_name

    @property
    def file_name(self) -> str:
        file_name = self.image_name
        if "." not in file_name:
            file_name += ".png"
        return file_name

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> dict[str, Any]:
        image = Image.open(os.path.join(src_path, self.file_name))
        self._merge_style_kwarg(kwargs)
        return self.make_image_dict(image, **kwargs)


class ForAnimation(ForProcessing):
    def __init__(
        self,
        *image_names: str,
        use_full_width: bool = False,
        duration: Union[int, list[int], tuple[int, ...]] | None = 1.0,
        **kwargs,
    ) -> None:
        image_names = tuple(image_names)
        if not image_names:
            raise ValueError("at least one image is required")

        super().__init__(**kwargs)
        self.image_names = image_names
        self.use_full_width = use_full_width
        self.duration = duration

    @property
    def file_names(self) -> tuple[str, ...]:
        return tuple(x if "." in x else x + ".png" for x in self.image_names)

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> dict[str, Any]:
        bytes_io, kwargs = self._make_frames(src_path, body_image, **kwargs)
        return self.make_image_dict(bytes_io, **kwargs)

    def _make_frames(
        self, src_path: str, body_image: Image, **kwargs
    ) -> tuple[BytesIO, dict[str, Any]]:
        frames = [
            Image.open(os.path.join(src_path, file_name)).convert("RGBA")
            for file_name in self.file_names
        ]

        bboxes = [x.getbbox() for x in frames]
        bboxes_iter = iter(bboxes)
        min_x, min_y, max_sx, max_sy = next(bboxes_iter)
        for x, y, sx, sy in bboxes_iter:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_sx = max(max_sx, sx)
            max_sy = max(max_sy, sy)

        cropped_frames = [
            frame.crop((min_x, min_y, max_sx, max_sy)) for frame in frames
        ]

        body_w, body_h = body_image.size

        width, height = (max_sx - min_x), (max_sy - min_y)
        width_pct = 100 * width / body_w
        height_pct = 100 * height / body_h

        style_vars = {
            "width": str(round(width_pct, 3)) + "%",
            "height": str(round(height_pct, 3)) + "%",
        }

        if self.use_full_width:
            left_pct = 100 * min_x / body_w
            top_pct = 100 * min_y / body_h
            style_vars["left"] = str(round(left_pct, 3)) + "%"
            style_vars["top"] = str(round(top_pct, 3)) + "%"

        self._merge_style_kwarg(kwargs, style_vars)

        bytes_io = BytesIO()
        cropped_frames_iter: Iterator[Image.Image] = iter(cropped_frames)
        # noinspection SpellCheckingInspection
        duration_coef = self.duration
        next(cropped_frames_iter).save(
            bytes_io,
            append_images=list(cropped_frames_iter),
            format=SAVE_FORMAT,
            save_all=True,
            duration=len(cropped_frames) if duration_coef is None else duration_coef,
        )

        return bytes_io, kwargs


class ForTrimming(ForAnimation):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, use_full_width=True, **kwargs)


class ForPlaceholder(ForTrimming):
    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> dict[str, Any]:
        self._merge_style_kwarg(kwargs, {"opacity": 0.0})
        return super().as_dict(src_path, pandora_id, body_image, **kwargs)


_TImage = ForProcessing | str | dict[str, Any] | None
_TBinary = tuple[_TImage, _TImage]


@attr.s(slots=True)
class CarType:
    body: str = attr.ib()
    driver_door: _TBinary | None = attr.ib(default=None)
    passenger_door: _TBinary | None = attr.ib(default=None)
    left_back_door: _TBinary | None = attr.ib(default=None)
    right_back_door: _TBinary | None = attr.ib(default=None)
    trunk: _TBinary | None = attr.ib(default=None)
    hood: _TBinary | None = attr.ib(default=None)
    parking: _TBinary | None = attr.ib(default=None)
    brakes: _TBinary | None = attr.ib(default=None)
    ignition: _TBinary | None = attr.ib(default=None)

    engine: _TBinary | None = attr.ib(default=None)
    engine_hood_open: _TBinary | None = attr.ib(default=None)

    alarm: _TBinary | None = attr.ib(default=None)
    active_security: _TBinary | None = attr.ib(default=None)
    service_mode: _TBinary | None = attr.ib(default=None)

    @staticmethod
    def condition_elements(
        elements: Union[list[dict[str, Any]], dict[str, Any]],
        condition_1: dict[str, Any],
        *conditions: dict[str, Any],
    ):
        return {
            "type": "conditional",
            "conditions": [condition_1, *conditions],
            "elements": elements if isinstance(elements, list) else [elements],
        }

    @staticmethod
    def condition_card(
        card: dict[str, Any],
        condition_1: dict[str, Any],
        *conditions: dict[str, Any],
    ):
        return {
            "type": "conditional",
            "conditions": [condition_1, *conditions],
            "card": card,
        }

    @staticmethod
    def entity_is(entity_id: str, state: Any):
        return {
            "entity": entity_id,
            "state": state,
        }

    @staticmethod
    def entity_is_not(entity_id: str, state: Any):
        return {
            "entity": entity_id,
            "state_not": state,
        }

    def as_dict_picture(
        self, src_path: str, pandora_id: str, clickable: bool = True, **kwargs
    ):
        body_image = PIL.Image.open(os.path.join(src_path, self.body + ".png")).convert(
            "RGBA"
        )

        elements = []
        yaml_dict = {
            "type": "picture-elements",
            "image": ForProcessing.image_as_data_uri(body_image),
            "elements": elements,
            **kwargs,
        }

        def _pic_to_dict(pic_val: _TImage, entity: str | None = None, **kwargs_):
            if isinstance(pic_val, str):
                pic_val = ForSimple(pic_val)

            if clickable and entity is not None:
                kwargs_["entity"] = entity

            if isinstance(pic_val, ForProcessing):
                return pic_val.as_dict(src_path, pandora_id, body_image, **kwargs_)

            raise TypeError(f"bad type: {type(pic_val)}")

        def _add_elements(
            elems,
            pics: tuple[_TImage, _TImage],
            entity: str | None = None,
            cond_val: str = "on",
            cond_entity: str | None = None,
        ):
            if cond_entity is None:
                cond_entity = entity
            for picture, condition in zip(pics, (self.entity_is_not, self.entity_is)):
                if picture:
                    elems.append(
                        self.condition_elements(
                            _pic_to_dict(picture, entity),
                            condition(cond_entity, cond_val),
                        )
                    )

        ###
        #
        #
        for bin_sens_key in (
            "driver_door",
            "passenger_door",
            "left_back_door",
            "right_back_door",
            "trunk",
            "hood",
            "parking",
            "brakes",
            "ignition",
        ):
            bin_sens_options = getattr(self, bin_sens_key)
            if bin_sens_options is None:
                continue

            entity_id = f"binary_sensor.{pandora_id}_{bin_sens_key}"
            _add_elements(elements, bin_sens_options, entity_id)

        ###
        #
        #
        engine_elements = []
        if self.engine:
            engine_entity_id = f"switch.{pandora_id}_engine"
            _add_elements(elements, self.engine, engine_entity_id)

        if self.engine_hood_open:
            engine_entity_id = f"switch.{pandora_id}_engine"
            hood_engine_elements = []
            _add_elements(hood_engine_elements, self.engine_hood_open, engine_entity_id)

            entity_id = f"switch.{pandora_id}_hood"
            elements.append(
                self.condition_elements(
                    hood_engine_elements, self.entity_is(entity_id, "on")
                )
            )

            if engine_elements:
                elements.append(
                    self.condition_elements(
                        engine_elements, self.entity_is_not(entity_id, "on")
                    )
                )
        else:
            elements.extend(engine_elements)

        ###
        #
        #
        alarm_elements = []
        lock_entity_id = f"lock.{pandora_id}_central_lock"
        if self.alarm:
            _add_elements(alarm_elements, self.alarm, lock_entity_id, "unlocked")

        as_entity_id = f"lock.{pandora_id}_active_security"
        if self.active_security:
            as_elements = []
            pic_off, pic_on = self.active_security

            if pic_on:
                as_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=as_entity_id),
                        self.entity_is(as_entity_id, "on"),
                    )
                )

            if alarm_elements:
                if pic_off:
                    alarm_elements.append(_pic_to_dict(pic_off, entity=as_entity_id))
                as_elements.append(
                    self.condition_elements(
                        alarm_elements, self.entity_is_not(as_entity_id, "on")
                    )
                )
            elif pic_off:
                as_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=as_entity_id),
                        self.entity_is_not(as_entity_id, "on"),
                    )
                )
        else:
            as_elements = alarm_elements

        sm_entity_id = f"switch.{pandora_id}_service_mode"
        if self.service_mode:
            service_elements = []
            pic_off, pic_on = self.service_mode

            if pic_on:
                service_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=sm_entity_id),
                        self.entity_is(sm_entity_id, "on"),
                    )
                )

            if as_elements:
                if pic_off:
                    as_elements.append(
                        _pic_to_dict(pic_off, entity=sm_entity_id),
                    )
                service_elements.append(
                    self.condition_elements(
                        as_elements,
                        self.entity_is_not(sm_entity_id, "on"),
                    )
                )
            elif pic_off:
                service_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=sm_entity_id),
                        self.entity_is_not(sm_entity_id, "on"),
                    )
                )
        else:
            service_elements = as_elements

        if service_elements:
            elements.extend(service_elements)

        return yaml_dict

    def as_dict_controls(self, pandora_id: str, **kwargs):
        engine_entity_id = f"switch.{pandora_id}_engine"
        as_entity_id = f"switch.{pandora_id}_active_security"
        return {
            "type": "horizontal-stack",
            "cards": [
                self.condition_card(
                    {
                        "type": "button",
                        "tap_action": {
                            "action": "toggle",
                        },
                        "hold_action": {
                            "action": "call-service",
                            "service": "switch.turn_on",
                            "service_data": {
                                "entity_id": as_entity_id,
                            },
                        },
                        "show_name": False,
                        "show_state": False,
                        "entity": f"lock.{pandora_id}_central_lock",
                    },
                    self.entity_is_not(as_entity_id, "on"),
                ),
                self.condition_card(
                    {
                        "type": "button",
                        "tap_action": {
                            "action": "toggle",
                        },
                        "show_name": False,
                        "show_state": False,
                        "entity": as_entity_id,
                    },
                    self.entity_is(as_entity_id, "on"),
                ),
                self.condition_card(
                    {
                        "type": "button",
                        "tap_action": {
                            "action": "toggle",
                            "confirmation": {
                                "text": "Будет произведена попытка запуска двигателя автомобиля."
                            },
                        },
                        "show_name": False,
                        "show_state": False,
                        "entity": engine_entity_id,
                    },
                    self.entity_is_not(engine_entity_id, "on"),
                ),
                self.condition_card(
                    {
                        "type": "button",
                        "tap_action": {
                            "action": "toggle",
                            "confirmation": {
                                "text": "Будет произведена попытка остановки двигателя автомобиля."
                            },
                        },
                        "show_name": False,
                        "show_state": False,
                        "entity": engine_entity_id,
                    },
                    self.entity_is(engine_entity_id, "on"),
                ),
            ],
        }

    # noinspection PyMethodMayBeStatic
    def as_dict_gauges(
        self,
        pandora_id: str,
        severity_tacho: Mapping[str, int] | None = None,
        severity_fuel: Mapping[str, int] | None = None,
    ):
        tacho_dict = {
            "type": "gauge",
            "min": 0,
            "name": "Тахометр",
            "entity": f"sensor.{pandora_id}_tachometer",
            "needle": True,
        }

        if severity_tacho is None:
            severity_tacho = {
                "green": 0,
                "yellow": 4500,
                "red": 6500,
            }
        else:
            severity_tacho = dict(severity_tacho)

        if severity_tacho:
            tacho_dict["severity"] = severity_tacho

        fuel_dict = {
            "type": "gauge",
            "min": 0,
            "max": 100,
            "name": "Уровень топлива",
            "entity": f"sensor.{pandora_id}_fuel",
            "needle": True,
        }

        if severity_fuel is None:
            severity_fuel = {
                "green": 45,
                "yellow": 15,
                "red": 0,
            }
        else:
            severity_fuel = dict(severity_fuel)

        if severity_fuel:
            fuel_dict["severity"] = severity_fuel

        return {"type": "horizontal-stack", "cards": [tacho_dict, fuel_dict]}

    # noinspection PyMethodMayBeStatic
    def as_dict_glances(self, pandora_id: str):
        return {
            "type": "glance",
            "entities": [
                {"entity": x, "name": y}
                for x, y in {
                    f"sensor.{pandora_id}_balance": "Баланс",
                    f"sensor.{pandora_id}_mileage": "Пробег",
                    f"device_tracker.{pandora_id}_pandora": "Локация",
                    f"sensor.{pandora_id}_engine_temperature": "Двигатель",
                    f"sensor.{pandora_id}_interior_temperature": "Салон",
                    f"sensor.{pandora_id}_battery_voltage": "Напряжение",
                }.items()
            ],
            "show_name": True,
            "show_icon": True,
            "show_state": True,
            "state_color": True,
            "columns": 3,
        }

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        severity_tacho: Mapping[str, int] | None = None,
        severity_fuel: Mapping[str, int] | None = None,
        clickable: bool = True,
    ):
        cards = [
            self.as_dict_picture(src_path, pandora_id, clickable),
        ]

        if clickable:
            cards.append(self.as_dict_controls(pandora_id))

        cards.extend(
            [
                self.as_dict_glances(pandora_id),
                self.as_dict_gauges(pandora_id, severity_tacho, severity_fuel),
            ]
        )

        return {
            "type": "vertical-stack",
            "cards": cards,
        }


CAR_TYPES = {
    "default": CarType(
        body="car_body_light",
        left_back_door=(
            ForTrimming("door_back_left_closed"),
            ForTrimming("door_back_left_opened"),
        ),
        right_back_door=(
            ForTrimming("door_back_right_closed"),
            ForTrimming("door_back_right_opened"),
        ),
        driver_door=(
            ForTrimming("door_front_left_closed"),
            ForTrimming("door_front_left_opened"),
        ),
        passenger_door=(
            ForTrimming("door_front_right_closed"),
            ForTrimming("door_front_right_opened"),
        ),
        trunk=(ForPlaceholder("trunk_opened"), ForTrimming("trunk_opened")),
        hood=(ForPlaceholder("hood_opened"), ForTrimming("hood_opened")),
        parking=(None, ForTrimming("parking")),
        brakes=(None, ForTrimming("brake")),
        ignition=(None, ForTrimming("ignition")),
        engine=(
            None,
            ForTrimming("engine_start", "engine_start_rotated", duration=200),
        ),
        engine_hood_open=(
            None,
            ForTrimming(
                "engine_start_inverse",
                "engine_start_inverse_rotated",
                duration=200,
            ),
        ),
        alarm=(ForTrimming("alarm_on"), ForTrimming("alarm_off")),
        active_security=(None, ForTrimming("alarm_active_mode")),
        service_mode=(None, ForTrimming("alarm_service_mode")),
    ),
    "default_dark": CarType(
        body="car_body_dark",
        left_back_door=(
            ForTrimming("door_back_left_closed_dark"),
            ForTrimming("door_back_left_opened_dark"),
        ),
        right_back_door=(
            ForTrimming("door_back_right_closed_dark"),
            ForTrimming("door_back_right_opened_dark"),
        ),
        driver_door=(
            ForTrimming("door_front_left_closed_dark"),
            ForTrimming("door_front_left_opened_dark"),
        ),
        passenger_door=(
            ForTrimming("door_front_right_closed_dark"),
            ForTrimming("door_front_right_opened_dark"),
        ),
        trunk=(ForPlaceholder("trunk_opened_dark"), ForTrimming("trunk_opened_dark")),
        hood=(ForPlaceholder("hood_opened_dark"), ForTrimming("hood_opened_dark")),
        parking=(None, ForTrimming("parking_dark")),
        brakes=(None, ForTrimming("brake_dark")),
        ignition=(None, ForTrimming("ignition_dark")),
        engine=(
            None,
            ForTrimming("engine_start_dark", "engine_start_rotated_dark", duration=200),
        ),
        engine_hood_open=(
            None,
            ForTrimming(
                "engine_start_inverse",
                "engine_start_inverse_rotated",
                duration=200,
            ),
        ),
        alarm=(ForTrimming("alarm_on"), ForTrimming("alarm_off_dark")),
        active_security=(None, ForTrimming("alarm_active_mode_dark")),
        service_mode=(None, ForTrimming("alarm_service_mode_dark")),
    ),
    # "hatchback": CarType(
    #     body="hatchback_body_light",
    #     left_back_door=(
    #         ForTrimming("hatchback_door_back_left_closed"),
    #         None,
    #     ),
    #     right_back_door=(
    #         ForTrimming("hatchback_door_back_right_closed"),
    #         None,
    #     ),
    #     driver_door=(
    #         ForTrimming("hatchback_door_front_left_closed"),
    #         None,
    #     ),
    #     passenger_door=(
    #         ForTrimming("hatchback_door_front_right_closed"),
    #         None,
    #     ),
    # ),
}


def extract_images(
    apk_file_path: str | BytesIO | bytes | bytearray,
    output_path: str,
    cleanup: bool = False,
) -> None:
    if isinstance(apk_file_path, (bytes, bytearray)):
        data = BytesIO(apk_file_path)
    elif not isinstance(apk_file_path, str):
        data = apk_file_path
    elif "://" in apk_file_path:
        response = requests.get(
            apk_file_path,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            allow_redirects=True,
        )
        response.raise_for_status()
        data = BytesIO(response.content)
    elif os.path.isfile(apk_file_path):
        with open(apk_file_path, "rb") as f:
            data = BytesIO(f.read())
    else:
        raise RuntimeError("apk not found")
    if not os.path.isdir(output_path):
        raise RuntimeError("output path does not exist")

    extension = ".png"
    if cleanup:
        for f in os.listdir(output_path):
            if not f.endswith(extension):
                continue
            path_f = os.path.join(output_path, f)
            if not os.path.isfile(path_f):
                continue
            os.unlink(path_f)

    import zipfile
    import shutil

    try:
        with zipfile.ZipFile(data) as zip_ref:
            for member in zip_ref.namelist():
                if member.startswith("res/") and member.endswith(extension):
                    filename = os.path.basename(member)
                    target_path = os.path.join(output_path, filename)
                    if os.path.isfile(target_path):
                        member_info = zip_ref.getinfo(member)
                        if not member_info.is_dir():
                            old_size = os.path.getsize(target_path)
                            new_size = member_info.file_size
                            if old_size >= new_size:
                                # Skip images larger than already found
                                continue
                            os.unlink(target_path)
                    with (
                        zip_ref.open(member) as source,
                        open(target_path, "wb") as target,
                    ):
                        shutil.copyfileobj(source, target)
    except zipfile.BadZipfile:
        print(data.read())
        raise


def make_cards(pandora_id: str, images_path: str):
    from glob import glob
    from yaml import dump

    cards_path = os.path.join(BASE_PATH, "cards")
    stacks_path = os.path.join(BASE_PATH, "stacks")
    dashboards_path = os.path.join(BASE_PATH, "dashboards")

    for path in (cards_path, dashboards_path, stacks_path):
        if os.path.isdir(path):
            for f in glob(os.path.join(path, "*.yaml")):
                os.unlink(f)
        else:
            os.mkdir(path)

    for clickable in (True, False):
        for key_type, car_type in CAR_TYPES.items():
            file_name = key_type
            if not clickable:
                file_name += "_non_interactive"
            file_name += ".yaml"

            card_config = car_type.as_dict_picture(images_path, pandora_id, clickable)
            card_str = dump(card_config, allow_unicode=True)
            with open(os.path.join(cards_path, file_name), "w", encoding="utf-8") as f:
                f.write(card_str)

            stack_config = car_type.as_dict(
                images_path, pandora_id, clickable=clickable
            )
            stack_str = dump(stack_config, allow_unicode=True)
            with open(os.path.join(stacks_path, file_name), "w", encoding="utf-8") as f:
                f.write(stack_str)

            panel_config = {
                "title": "Pandora CAS",
                "views": [
                    {
                        "type": "sidebar",
                        "title": "Автомобиль",
                        "cards": [
                            {
                                "type": "map",
                                "view_layout": {"position": "main"},
                                "hours_to_show": 24,
                                "entities": [
                                    {"entity": f"device_tracker.{pandora_id}_pandora"}
                                ],
                            },
                            {
                                **stack_config,
                                "view_layout": {"position": "sidebar"},
                            },
                        ],
                    }
                ],
            }

            dashboard_str = dump(panel_config, allow_unicode=True)
            with open(
                os.path.join(dashboards_path, file_name),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(dashboard_str)

    print(f"Generated configuration for Pandora ID: {pandora_id}")


def url_or_file(value: str) -> str:
    return value if "://" in value else argparse.FileType("rb")(value)


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("pandora_id", help="Pandora Device ID")
    parser.add_argument("apk", type=url_or_file)
    args = parser.parse_args()
    pandora_id = args.pandora_id or "REPLACE_WITH_PANDORA_ID"

    with tempfile.TemporaryDirectory() as temp_dir:
        extract_images(args.apk, temp_dir)
        make_cards(pandora_id, temp_dir)


if __name__ == "__main__":
    main()
