#!/usr/bin/env python3
import importlib
import json
import os
from typing import Any

import deepmerge
from homeassistant.const import ATTR_NAME

import custom_components.pandora_cas as m
from custom_components.pandora_cas.const import PLATFORMS, ATTR_DEVICE_ID
from custom_components.pandora_cas.entity import PandoraCASEntityDescription

platform_entry_names: dict[str, dict[str, str]] = {}

for platform in PLATFORMS:
    module = importlib.import_module(f"custom_components.pandora_cas.{platform}")
    if not (entity_types := getattr(module, "ENTITY_TYPES", None)):
        continue
    entity_type: PandoraCASEntityDescription
    all_types = platform_entry_names.setdefault(str(platform), {})
    for entity_type in entity_types:
        all_types[entity_type.key] = entity_type.name

default_attributes = {ATTR_DEVICE_ID: "Device Identifier"}

default_attributes_per_language = {"ru": {ATTR_DEVICE_ID: "Идентификатор устройства"}}


def get_translations(in_dict):
    return {key: {ATTR_NAME: value} for key, value in in_dict.items()}


path_root = os.path.dirname(m.__file__)

strings: dict[str, Any]
with open(
    strings_path := os.path.join(path_root, "strings.json"), "r", encoding="utf-8"
) as fp:
    print(f"Loading strings from {strings_path}")
    strings = json.load(fp)

strings_entities = strings.setdefault("entity", {})
for platform, entries in platform_entry_names.items():
    if not (strings_platform := strings_entities.setdefault(platform, {})):
        print(f"Platform {platform} not found in strings")
    for entry, expected_name in entries.items():
        if not (settings := strings_platform.setdefault(entry, {})):
            print(f"Platform {platform} key {entry} does not exist")
        elif (entry_name := settings.get("name")) != expected_name:
            print(
                f"Platform {platform} key {entry} does not match: {entry_name} != {expected_name}"
            )
        settings.setdefault("name", expected_name)
        settings["state_attributes"] = deepmerge.conservative_merger.merge(
            settings.get("state_attributes") or {},
            get_translations(default_attributes),
        )
with open(strings_path, "w", encoding="utf-8") as fp:
    print(f"Writing strings to {strings_path}")
    json.dump(strings, fp, ensure_ascii=False, indent=2, sort_keys=True)
for language_file in os.listdir(
    translations_root := os.path.join(path_root, "translations")
):
    language_file_path = os.path.join(translations_root, language_file)
    if not (os.path.isfile(language_file_path) and language_file.endswith(".json")):
        continue
    language = language_file.rpartition(".")[0]
    language_strings: dict[str, Any]
    with open(language_file_path, "r", encoding="utf-8") as fp:
        print(f"Loading strings from {language_file_path}")
        language_strings = json.load(fp)
    language_strings = deepmerge.conservative_merger.merge(language_strings, strings)
    for platform, entries in platform_entry_names.items():
        strings_platform = language_strings["entity"][platform]
        for entry, expected_name in entries.items():
            settings = strings_platform[entry]
            settings.setdefault("name", expected_name)
            settings["state_attributes"] = deepmerge.conservative_merger.merge(
                settings.get("state_attributes") or {},
                get_translations(default_attributes),
            )
    with open(language_file_path, "w", encoding="utf-8") as fp:
        json.dump(language_strings, fp, ensure_ascii=False, indent=2, sort_keys=True)
