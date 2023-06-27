import os
from base64 import b64encode
from io import BytesIO
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, Union

import PIL.ImageChops
import attr
from PIL import Image


class NotSet(object):
    ...


NOT_SET = NotSet()
BASE_PATH = os.path.dirname(__file__)
SRC_PATH = os.path.join(BASE_PATH, "images")

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
    def __init__(
        self, *, base_style: Optional[Mapping[str, Any]] = None
    ) -> None:
        self._base_style = _BASE_STYLE
        if base_style:
            self._base_style.update(base_style)

    @classmethod
    def image_as_data_uri(
        cls, image: Union[bytes, BytesIO, Image.Image]
    ) -> str:
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
    ) -> Dict[str, Any]:
        return {
            "type": "image",
            "image": cls.image_as_data_uri(image),
            **kwargs,
        }

    def get_style(
        self, style: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        return (
            dict(self._base_style)
            if style is None
            else {**self._base_style, **style}
        )

    def _merge_style_kwarg(
        self, kwargs: Dict[str, Any], style: Optional[Mapping[str, Any]] = None
    ) -> None:
        final_styles = dict(self._base_style)
        final_styles.update(style or {})
        final_styles.update(kwargs.pop("style", None) or {})

        if final_styles:
            kwargs["style"] = final_styles

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ForSimple(ForProcessing):
    def __init__(self, image_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._image_name = image_name

    @property
    def file_name(self) -> str:
        file_name = self._image_name
        if "." not in file_name:
            file_name += ".png"
        return file_name

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> Dict[str, Any]:
        image = Image.open(os.path.join(src_path, self.file_name))
        self._merge_style_kwarg(kwargs)

        return self.make_image_dict(image, **kwargs)


class ForAnimation(ForProcessing):
    def __init__(
        self,
        *image_names: str,
        use_full_width: bool = False,
        duration: Optional[Union[int, List[int], Tuple[int, ...]]] = 1.0,
        **kwargs,
    ) -> None:
        image_names = tuple(image_names)
        if not image_names:
            raise ValueError("at least one image is required")

        super().__init__(**kwargs)
        self._image_names = image_names
        self._use_full_width = use_full_width

        self.duration = duration

    @property
    def file_names(self) -> Tuple[str, ...]:
        return tuple(x if "." in x else x + ".png" for x in self._image_names)

    def as_dict(
        self,
        src_path: str,
        pandora_id: str,
        body_image: Image,
        **kwargs,
    ) -> Dict[str, Any]:
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

        if self._use_full_width:
            left_pct = 100 * min_x / body_w
            top_pct = 100 * min_y / body_h
            style_vars["left"] = str(round(left_pct, 3)) + "%"
            style_vars["top"] = str(round(top_pct, 3)) + "%"

        self._merge_style_kwarg(kwargs, style_vars)

        bytes_io = BytesIO()
        cropped_frames_iter: Iterator[Image.Image] = iter(cropped_frames)
        duration_coef = self.duration
        next(cropped_frames_iter).save(
            bytes_io,
            append_images=list(cropped_frames_iter),
            format=SAVE_FORMAT,
            save_all=True,
            duration=len(cropped_frames)
            if duration_coef is None
            else duration_coef,
        )

        return self.make_image_dict(bytes_io, **kwargs)


class ForTrimming(ForAnimation):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, use_full_width=True, **kwargs)


_TImage = Optional[Union[ForProcessing, str, Dict[str, Any]]]
_TBinary = Tuple[_TImage, _TImage]


@attr.s(slots=True)
class CarType:
    body: str = attr.ib()
    driver_door: Optional[_TBinary] = attr.ib(default=None)
    passenger_door: Optional[_TBinary] = attr.ib(default=None)
    left_back_door: Optional[_TBinary] = attr.ib(default=None)
    right_back_door: Optional[_TBinary] = attr.ib(default=None)
    trunk: Optional[_TBinary] = attr.ib(default=None)
    hood: Optional[_TBinary] = attr.ib(default=None)
    parking: Optional[_TBinary] = attr.ib(default=None)
    brakes: Optional[_TBinary] = attr.ib(default=None)
    ignition: Optional[_TBinary] = attr.ib(default=None)

    engine: Optional[_TBinary] = attr.ib(default=None)
    engine_hood_open: Optional[_TBinary] = attr.ib(default=None)

    alarm: Optional[_TBinary] = attr.ib(default=None)
    active_security: Optional[_TBinary] = attr.ib(default=None)
    service_mode: Optional[_TBinary] = attr.ib(default=None)

    @staticmethod
    def condition_elements(
        elements: Union[List[Dict[str, Any]], Dict[str, Any]],
        condition_1: Dict[str, Any],
        *conditions: Dict[str, Any],
    ):
        return {
            "type": "conditional",
            "conditions": [condition_1, *conditions],
            "elements": elements if isinstance(elements, list) else [elements],
        }

    @staticmethod
    def condition_card(
        card: Dict[str, Any],
        condition_1: Dict[str, Any],
        *conditions: Dict[str, Any],
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

    def as_dict_picture(self, src_path: str, pandora_id: str, **kwargs):
        body_image = PIL.Image.open(
            os.path.join(src_path, self.body + ".png")
        ).convert("RGBA")

        elements = []
        yaml_dict = {
            "type": "picture-elements",
            "image": ForProcessing.image_as_data_uri(body_image),
            "elements": elements,
            **kwargs,
        }

        def _pic_to_dict(pic_val: _TImage, **kwargs_):
            if isinstance(pic_val, str):
                pic_val = ForSimple(pic_val)

            if isinstance(pic_val, ForProcessing):
                return pic_val.as_dict(
                    src_path, pandora_id, body_image, **kwargs_
                )

            raise TypeError

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

            pic_off, pic_on = bin_sens_options
            entity_id = f"binary_sensor.{pandora_id}_{bin_sens_key}"

            if pic_on:
                elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=entity_id),
                        self.entity_is(entity_id, "on"),
                    )
                )

            if pic_off:
                elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=entity_id),
                        self.entity_is_not(entity_id, "on"),
                    )
                )

        ###
        #
        #
        engine_elements = []
        if self.engine:
            pic_off, pic_on = self.engine
            engine_entity_id = f"switch.{pandora_id}_engine"

            if pic_on:
                elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=engine_entity_id),
                        self.entity_is(engine_entity_id, "on"),
                    )
                )

            if pic_off:
                elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=engine_entity_id),
                        self.entity_is_not(engine_entity_id, "on"),
                    )
                )

        if self.engine_hood_open:
            pic_off, pic_on = self.engine_hood_open
            engine_entity_id = f"switch.{pandora_id}_engine"

            hood_engine_elements = []
            if pic_on:
                hood_engine_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=engine_entity_id),
                        self.entity_is(engine_entity_id, "on"),
                    )
                )

            if pic_off:
                hood_engine_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=engine_entity_id),
                        self.entity_is_not(engine_entity_id, "on"),
                    )
                )

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
            pic_off, pic_on = self.alarm

            if pic_on:
                alarm_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_on, entity=lock_entity_id),
                        self.entity_is(lock_entity_id, "unlocked"),
                    )
                )

            if pic_off:
                alarm_elements.append(
                    self.condition_elements(
                        _pic_to_dict(pic_off, entity=lock_entity_id),
                        self.entity_is_not(lock_entity_id, "unlocked"),
                    )
                )

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
                    alarm_elements.append(
                        _pic_to_dict(pic_off, entity=as_entity_id)
                    )
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

    def as_dict_gauges(
        self,
        pandora_id: str,
        severity_tacho: Optional[Mapping[str, int]] = None,
        severity_fuel: Optional[Mapping[str, int]] = None,
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
        severity_tacho: Optional[Mapping[str, int]] = None,
        severity_fuel: Optional[Mapping[str, int]] = None,
    ):
        return {
            "type": "vertical-stack",
            "cards": [
                self.as_dict_picture(src_path, pandora_id),
                self.as_dict_controls(pandora_id),
                self.as_dict_glances(pandora_id),
                self.as_dict_gauges(pandora_id, severity_tacho, severity_fuel),
            ],
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
        trunk=(None, ForTrimming("trunk_opened")),
        hood=(None, ForTrimming("hood_opened")),
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
        trunk=(None, ForTrimming("trunk_opened_dark")),
        hood=(None, ForTrimming("hood_opened_dark")),
        parking=(None, ForTrimming("parking_dark")),
        brakes=(None, ForTrimming("brake_dark")),
        ignition=(None, ForTrimming("ignition_dark")),
        engine=(
            None,
            ForTrimming(
                "engine_start_dark", "engine_start_rotated_dark", duration=200
            ),
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


def main():
    from yaml import dump
    from glob import glob
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("pandora_id", nargs="?")

    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--copy-card", choices=CAR_TYPES.keys())
    grp.add_argument("--copy-dashboard", choices=CAR_TYPES.keys())
    grp.add_argument("--copy-stack", choices=CAR_TYPES.keys())

    args = parser.parse_args()
    pandora_id = args.pandora_id or "REPLACE_WITH_PANDORA_ID"

    cards_path = os.path.join(BASE_PATH, "cards")
    stacks_path = os.path.join(BASE_PATH, "stacks")
    dashboards_path = os.path.join(BASE_PATH, "dashboards")

    for path in (cards_path, dashboards_path, stacks_path):
        if os.path.isdir(path):
            for f in glob(os.path.join(path, "*.yaml")):
                os.unlink(f)
        else:
            os.mkdir(path)

    to_copy = None
    for key_type, car_type in CAR_TYPES.items():
        file_name = key_type + ".yaml"

        card_config = car_type.as_dict_picture(SRC_PATH, pandora_id)
        card_str = dump(card_config, allow_unicode=True)
        if args.copy_card == key_type:
            to_copy = card_str
        with open(
            os.path.join(cards_path, file_name), "w", encoding="utf-8"
        ) as f:
            f.write(card_str)

        stack_config = car_type.as_dict(SRC_PATH, pandora_id)
        stack_str = dump(stack_config, allow_unicode=True)
        if args.copy_stack == key_type:
            to_copy = stack_str
        with open(
            os.path.join(stacks_path, file_name), "w", encoding="utf-8"
        ) as f:
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
                                {
                                    "entity": f"device_tracker.{pandora_id}_pandora"
                                }
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
        if args.copy_dashboard == key_type:
            to_copy = dashboard_str

        with open(
            os.path.join(dashboards_path, file_name),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(dashboard_str)

    print(f"Generated configuration for Pandora ID: {pandora_id}")

    if to_copy:
        import pyperclip

        pyperclip.copy(to_copy)
        copy_key = args.copy_card or args.copy_dashboard or args.copy_stack
        copy_type = (
            "card"
            if args.copy_card
            else "stack"
            if args.copy_stack
            else "dashboard"
        )
        print(f"Copied '{copy_key}' {copy_type} configuration to clipboard")

    exit(0)


if __name__ == "__main__":
    main()
