#!/usr/bin/env python3
import importlib
import json
import os.path
from typing import Any

import deepmerge
from homeassistant.const import ATTR_NAME, ATTR_DEVICE_ID
from homeassistant.util.yaml import load_yaml_dict, save_yaml

import custom_components.pandora_cas as m
from custom_components.pandora_cas.const import PLATFORMS, DOMAIN
from custom_components.pandora_cas.entity import PandoraCASEntityDescription
from pandora_cas.enums import CommandID, CommandParams

try:
    from yaml import CSafeDumper as FastestAvailableSafeDumper
except ImportError:
    from yaml import (  # type: ignore[assignment]
        SafeDumper as FastestAvailableSafeDumper,
    )

# Use almost-default merge strategies, except for list
MERGE_STRATEGIES = deepmerge.DEFAULT_TYPE_SPECIFIC_MERGE_STRATEGIES.copy()
for i, (cls, strategy) in enumerate(MERGE_STRATEGIES):
    if cls in (list, set):
        MERGE_STRATEGIES[i] = (cls, "override")

always_merger = deepmerge.Merger(MERGE_STRATEGIES, ["override"], ["override"])

# Retrieve platforms
platform_entry_names: dict[str, dict[str, str]] = {}

for platform in PLATFORMS:
    module = importlib.import_module(f"custom_components.pandora_cas.{platform}")
    if not (entity_types := getattr(module, "ENTITY_TYPES", None)):
        continue
    entity_type: PandoraCASEntityDescription
    all_types = platform_entry_names.setdefault(str(platform), {})
    for entity_type in entity_types:
        all_types[entity_type.key] = entity_type.name

# Retrieve services
commands: dict[int, str] = dict(map(reversed, m.iterate_commands_to_register()))

default_attributes = {ATTR_DEVICE_ID: "Pandora Device"}
default_attributes_per_language = {"ru": {ATTR_DEVICE_ID: "Устройство Pandora"}}


def get_translation_services(
    command_id: int,
    language: str | None = None,
) -> dict[str, Any]:
    command_slug = commands[command_id]
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
        "device_id": (
            {
                "description": "Объект / идентификатор устройства Home Assistant.",
                "name": "Устройство Home Assistant",
            }
            if language == "ru"
            else {
                "description": "Home Assistant device object / identifier.",
                "name": "Home Assistant Device",
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


def get_services(
    command_id: int,
    russian_name: str | None = None,
    english_name: str | None = None,
    current_name: str | None = None,
) -> dict[str, Any]:
    service_fields = {
        ATTR_DEVICE_ID: {
            "description": "Pandora device identifier (`PANDORA_ID`, `device_id`)",
            "example": 1234567,
            "selector": {"text": None},
        },
        "device": {
            "description": f"Home Assistant device within the `{DOMAIN}` integration domain",
            "selector": {
                "device": {
                    "filter": [
                        {
                            "integration": DOMAIN,
                        }
                    ]
                }
            },
        },
    }

    if command_id == CommandID.CLIMATE_SET_TEMPERATURE:
        service_fields[str(CommandParams.CLIMATE_TEMP)] = {
            "description": "Target temperature to maintain within the interior.",
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

    if russian_name is None:
        russian_name = (
            f"Удалённая команда {commands[command_id].upper()} ({command_id})"
        )
    if english_name is None:
        english_name = f"Remote command {commands[command_id].upper()} ({command_id})"
    return {
        "description": current_name or (russian_name + " / " + english_name),
        "fields": service_fields,
    }


def get_translations(language: str | None = None):
    # @TODO: add translations for entities
    return {key: {ATTR_NAME: value} for key, value in default_attributes.items()}


path_root = os.path.dirname(m.__file__)


def process_translations(target_strings, language: str | None = None):
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
    for command_id, command_slug in commands.items():
        services_strings[command_slug] = deepmerge.conservative_merger.merge(
            services_strings.get(command_slug) or {},
            get_translation_services(command_id, language),
        )
        services_strings[command_slug]["fields"] = always_merger.merge(
            services_strings[command_slug].get("fields") or {},
            get_translation_services_fields(command_id, language),
        )


class StringsLoader:
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
            json.dump(self._data, fp, ensure_ascii=False, indent=2, sort_keys=True)


# Process basic strings
strings: dict[str, Any]
with StringsLoader(os.path.join(path_root, "strings.json")) as strings:
    process_translations(strings)

# Process localized strings
russian_strings: dict[str, Any] | None = None
english_strings: dict[str, Any] | None = None
language_strings: dict[str, Any]
for language_file in os.listdir(
    translations_root := os.path.join(path_root, "translations")
):
    language_file_path = os.path.join(translations_root, language_file)
    if not (os.path.isfile(language_file_path) and language_file.endswith(".json")):
        continue
    language_code = language_file.rpartition(".")[0]
    with StringsLoader(language_file_path) as language_strings:
        language_strings = deepmerge.conservative_merger.merge(
            language_strings, strings
        )
        process_translations(language_strings, language_code)
        if language_code == "ru":
            russian_strings = language_strings
        elif language_code == "en":
            english_strings = language_strings

# Process services YAML
services_yaml = load_yaml_dict(
    services_path := os.path.join(path_root, "services.yaml")
)
for command_id, command_slug in commands.items():
    russian_name = russian_strings.get("services", {}).get(command_slug, {}).get("name")
    english_name = english_strings.get("services", {}).get(command_slug, {}).get("name")
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
