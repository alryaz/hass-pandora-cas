import importlib
from typing import Iterable

from custom_components.pandora_cas.entity import PandoraCASEntityDescription


def iterate_platform_entity_types(platforms: Iterable[str] | None = None):
    if platforms is None:
        from custom_components.pandora_cas.const import PLATFORMS
        platforms = PLATFORMS
    for platform in platforms:
        module = importlib.import_module(f"custom_components.pandora_cas.{platform}")
        if not (entity_types := getattr(module, "ENTITY_TYPES", None)):
            continue
        for entity_type in entity_types:
            yield platform, entity_type