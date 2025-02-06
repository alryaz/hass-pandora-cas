#!/usr/bin/env python3
import attr

from pandora_cas.data import CurrentState
from pandora_cas.device import PandoraOnlineDevice
from tools.helpers import iterate_platform_entity_types

per_attribute_gets = {}
for platform, entity_type in iterate_platform_entity_types():
    attribute = getattr(entity_type, "attribute", None)
    attribute_source = getattr(entity_type, "attribute_source", None)
    if attribute is None:
        continue
    per_attribute_gets.setdefault(attribute_source, set()).add(attribute)

for attribute_source, attribute_get in per_attribute_gets.items():
    source_value = PandoraOnlineDevice
    ignored = set()
    if attribute_source == "state":
        source_value = CurrentState
        ignored.update(("imei",))
    else:
        print(f"Unknown attribute source {attribute_source}")
        continue
    ignored.update(attribute_get)
    for attribute in attr.fields(source_value):
        if attribute.name not in ignored:
            print(f"Unused attribute {attribute.name} in {attribute_source}")
