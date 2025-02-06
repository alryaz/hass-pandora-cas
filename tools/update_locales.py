#!/usr/bin/env python3
import importlib
import json
import os.path
from typing import Any

import deepmerge
from homeassistant.const import ATTR_NAME, ATTR_DEVICE_ID
from homeassistant.util.yaml import load_yaml_dict, save_yaml

import custom_components.pandora_cas as m
import custom_components.pandora_cas.services
from custom_components.pandora_cas.const import PLATFORMS, ATTR_ENSURE_COMPLETE, DOMAIN
from custom_components.pandora_cas.entity import PandoraCASEntityDescription
from custom_components.pandora_cas.services import SERVICE_REMOTE_COMMAND
from pandora_cas.enums import CommandID, CommandParams
from tools.helpers import iterate_platform_entity_types

try:
    from yaml import CSafeDumper as FastestAvailableSafeDumper
except ImportError:
    from yaml import (  # type: ignore[assignment]
        SafeDumper as FastestAvailableSafeDumper,
    )

COMPONENT_ROOT = os.path.dirname(m.__file__)

# Use almost-default merge strategies, except for list
MERGE_STRATEGIES = deepmerge.DEFAULT_TYPE_SPECIFIC_MERGE_STRATEGIES.copy()
for i, (cls, strategy) in enumerate(MERGE_STRATEGIES):
    if cls in (list, set):
        MERGE_STRATEGIES[i] = (cls, "override")

always_merger = deepmerge.Merger(MERGE_STRATEGIES, ["override"], ["override"])

# Retrieve services
# noinspection PyTypeChecker
COMMAND_SLUGS_BY_ID: dict[int, str] = dict(
    map(reversed, custom_components.pandora_cas.services.iterate_commands_to_register())
)
DEFAULT_ATTRIBUTES_STRINGS = {ATTR_DEVICE_ID: "Pandora Device"}
DEFAULT_ATTRIBUTES_TRANSLATE = {"ru": {ATTR_DEVICE_ID: "Устройство Pandora"}}


class JSONContext:
    def __init__(self, path: str) -> None:
        self._path = path
        self._data = None

    def __enter__(self) -> dict[str, Any]:
        with open(self._path, "r", encoding="utf-8") as fp:
            print(f"Loading strings from {self._path}")
            self._data = json.load(fp)
        return self._data

    def __exit__(self, exc_type, exc_val, exc_tb):
        with open(self._path, "w", encoding="utf-8") as fp:
            print(f"Writing strings to {self._path}")
            fp.write(
                json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True)
            )


def get_translation_services(
    command_id: int,
    language: str | None = None,
) -> dict[str, Any]:
    command_slug = COMMAND_SLUGS_BY_ID[command_id]
    return {
        "name": command_slug.replace("_", " ").title(),
        "description": (
            (
                "Выполнить команду на удалённом устройстве"
                if language == "ru"
                else "Execute command on the remote device"
            )
            + ": "
            + command_slug.upper()
            + " ("
            + str(command_id)
            + ")"
        ),
    }


def get_translation_services_fields(
    command_id: int, language: str | None = None
) -> dict[str, Any]:
    service_fields = {
        ATTR_DEVICE_ID: (
            {
                "description": "Уникальный числовой идентификатор целевого устройства Pandora, или объект устройства в Home Assistant.",
                "name": "Устройство Pandora",
            }
            if language == "ru"
            else {
                "description": "Home Assistant device object / identifier.",
                "name": "Home Assistant Device",
            }
        ),
        ATTR_ENSURE_COMPLETE: (
            {
                "description": "Ожидать окончания выполнения отправки команды.",
                "name": "Ожидать завершения",
            }
            if language == "ru"
            else {
                "description": "Ensure the command gets sent successfully.",
                "name": "Ensure completion",
            }
        ),
    }

    if command_id == CommandID.CLIMATE_SET_TEMPERATURE:
        service_fields[str(CommandParams.CLIMATE_TEMP)] = (
            {
                "description": "Целевая температура, необходимая для поддержания в салоне.",
                "name": "Целевая температура",
            }
            if language == "ru"
            else {
                "description": "Target temperature to maintain within the interior.",
                "name": "Target Temperature",
            }
        )

    return service_fields


# noinspection PyUnusedLocal
def get_services(
    command_id: int,
    russian_name: str | None = None,
    english_name: str | None = None,
    current_name: str | None = None,
) -> dict[str, Any]:
    service_fields = {
        ATTR_DEVICE_ID: {
            # "description": "Pandora device identifier (`PANDORA_ID`, `device_id`)",
            "example": 1234567,
            "selector": {"device": {"integration": DOMAIN}},
        },
        # "device": {
        #     # "description": f"Home Assistant device within the `{DOMAIN}` integration domain",
        #     "selector": {
        #         "device": {
        #             "integration": DOMAIN,
        #         }
        #     },
        # },
        ATTR_ENSURE_COMPLETE: {
            "example": True,
            "default": False,
            "selector": {"boolean": None},
        },
    }

    if command_id == CommandID.CLIMATE_SET_TEMPERATURE:
        service_fields[str(CommandParams.CLIMATE_TEMP)] = {
            # "description": "Target temperature to maintain within the interior.",
            "example": 18,
            "selector": {
                "number": {
                    "min": 16,
                    "max": 33,
                    "step": 1,
                    "unit_of_measurement": "°C",
                }
            },
        }

    # if russian_name is None:
    #     russian_name = (
    #         f"Удалённая команда {command_slugs_by_id[command_id].upper()} ({command_id})"
    #     )
    # if english_name is None:
    #     english_name = f"Remote command {command_slugs_by_id[command_id].upper()} ({command_id})"
    return {
        # "description": current_name or (russian_name + " / " + english_name),
        "fields": service_fields,
    }


# noinspection PyUnusedLocal
def get_translations(language: str | None = None):
    # @TODO: add translations for entities
    return {
        key: {ATTR_NAME: value} for key, value in DEFAULT_ATTRIBUTES_STRINGS.items()
    }


def process_translations(
    platform_entry_names, target_strings, language: str | None = None
):
    # Process platforms
    entities_strings = target_strings.setdefault("entity", {})
    for platform, entries in platform_entry_names.items():
        strings_platform = entities_strings.setdefault(platform, {})
        for entry, expected_name in entries.items():
            settings = strings_platform.setdefault(entry, {})
            settings.setdefault("name", expected_name)
            settings["state_attributes"] = deepmerge.conservative_merger.merge(
                settings.get("state_attributes") or {},
                get_translations(language),
            )

    # Process services
    services_strings = target_strings.setdefault("services")
    for command_id, command_slug in COMMAND_SLUGS_BY_ID.items():
        services_strings[command_slug] = deepmerge.conservative_merger.merge(
            services_strings.get(command_slug) or {},
            get_translation_services(command_id, language),
        )
        services_strings[command_slug]["fields"] = always_merger.merge(
            services_strings[command_slug].get("fields") or {},
            get_translation_services_fields(command_id, language),
        )

    remote_command_strings = services_strings.setdefault(SERVICE_REMOTE_COMMAND, {})
    remote_command_strings["fields"] = always_merger.merge(
        remote_command_strings.get("fields") or {},
        get_translation_services_fields(-1, language),
    )


def main():
    # Retrieve platforms
    platform_entry_names: dict[str, dict[str, str]] = {}
    command_icons: dict[str, str] = {}

    command_icons_search: dict[str, tuple[str, ...]] = {
        "command_on": ("icon_on", "icon"),
        "command_off": ("icon_off", "icon"),
        "command": ("icon",),
        "command_init": ("icon_min", "icon"),
        "command_set": ("icon",),
    }

    for platform, entity_type in iterate_platform_entity_types():
        all_types = platform_entry_names.setdefault(str(platform), {})
        all_types[entity_type.key] = entity_type.name

        for command_attr, order_of_icons in command_icons_search.items():
            command = getattr(entity_type, command_attr, None)
            if isinstance(command, dict):
                commands_identifiers = command.values()
            else:
                commands_identifiers = (command,)
            for command_identifier in commands_identifiers:
                if not isinstance(command_identifier, (int, CommandID)):
                    continue
                command_slug = COMMAND_SLUGS_BY_ID[int(command_identifier)]
                for icon_attr in order_of_icons:
                    icon = getattr(entity_type, icon_attr, None)
                    if icon:
                        command_icons.setdefault(command_slug, icon)
                        break

    with JSONContext(os.path.join(COMPONENT_ROOT, "icons.json")) as all_icons:
        all_icons["services"] = always_merger.merge(
            all_icons.get("services") or {}, command_icons
        )

    # Process basic strings
    strings: dict[str, Any]
    with JSONContext(os.path.join(COMPONENT_ROOT, "strings.json")) as strings:
        process_translations(platform_entry_names, strings)

    # Process localized strings
    russian_strings: dict[str, Any] | None = None
    english_strings: dict[str, Any] | None = None
    language_strings: dict[str, Any]
    for language_file in os.listdir(
        translations_root := os.path.join(COMPONENT_ROOT, "translations")
    ):
        language_file_path = os.path.join(translations_root, language_file)
        if not (os.path.isfile(language_file_path) and language_file.endswith(".json")):
            continue
        language_code = language_file.rpartition(".")[0]
        with JSONContext(language_file_path) as language_strings:
            language_strings = deepmerge.conservative_merger.merge(
                language_strings, strings
            )
            process_translations(platform_entry_names, language_strings, language_code)
            if language_code == "ru":
                russian_strings = language_strings
            elif language_code == "en":
                english_strings = language_strings

    # Process services YAML
    services_yaml = load_yaml_dict(
        services_path := os.path.join(COMPONENT_ROOT, "services.yaml")
    )
    services_yaml[SERVICE_REMOTE_COMMAND] = always_merger.merge(
        services_yaml.get(SERVICE_REMOTE_COMMAND) or {},
        get_services(-1, None, None, None),
    )

    for command_id, command_slug in COMMAND_SLUGS_BY_ID.items():
        russian_name = (
            russian_strings.get("services", {}).get(command_slug, {}).get("name")
        )
        english_name = (
            english_strings.get("services", {}).get(command_slug, {}).get("name")
        )
        services_yaml[command_slug] = always_merger.merge(
            services_yaml.get(command_slug) or {},
            get_services(
                command_id,
                russian_name,
                english_name,
                (services_yaml.get(command_slug) or {}).get("description"),
            ),
        )
    save_yaml(services_path, services_yaml)


if __name__ == "__main__":
    main()
