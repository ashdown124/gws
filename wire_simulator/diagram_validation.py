from __future__ import annotations

from collections.abc import Mapping

from .components import COMPONENT_PROPERTY_SCHEMAS, COMPONENT_STYLES
from .diagram_io import has_supported_envelope
from .editor_models import WIRE_COLORS


class DiagramValidationError(ValueError):
    """A diagram failed structural validation."""

    def __init__(self, message_key: str) -> None:
        super().__init__(message_key)
        self.message_key = message_key


def validate_diagram(
    data: dict[str, object], custom_switches: Mapping[str, object],
    missing_custom_switches: set[str] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not has_supported_envelope(data):
        raise DiagramValidationError("unsupported_diagram")
    component_records = data.get("components")
    wire_records = data.get("wires")
    if not isinstance(component_records, list) or not isinstance(wire_records, list):
        raise DiagramValidationError("invalid_diagram")

    component_fields = {"id", "kind", "x", "y", "properties", "gauge_value", "switch_position"}
    wire_fields = {"id", "color", "start", "end", "nodes"}
    loadable_components: list[dict[str, object]] = []
    excluded_component_ids: set[int] = set()
    for record in component_records:
        if not isinstance(record, dict) or not component_fields.issubset(record):
            raise DiagramValidationError("invalid_diagram")
        if "name" in record and not isinstance(record["name"], str):
            raise DiagramValidationError("invalid_diagram")
        kind = str(record["kind"])
        properties = record["properties"]
        if kind not in COMPONENT_STYLES or not isinstance(properties, dict):
            raise DiagramValidationError("invalid_diagram")
        required_properties: set[str] = set()
        for field in COMPONENT_PROPERTY_SCHEMAS.get(kind, []):
            required_properties.add(field["key"])
            if "units" in field:
                required_properties.add(f"{field['key']}_unit")
        if set(properties) != required_properties:
            raise DiagramValidationError("invalid_diagram")
        if kind == "jack" and properties.get("jack_type") != "mono":
            raise DiagramValidationError("invalid_diagram")
        rotation = record.get("rotation", 0)
        if not isinstance(rotation, int) or rotation not in (0, 90, 180, 270):
            raise DiagramValidationError("invalid_diagram")
        switch_type = str(properties.get("switch_type", ""))
        if (
            kind == "switch"
            and switch_type.startswith("custom:")
            and switch_type.removeprefix("custom:") not in custom_switches
        ):
            switch_name = switch_type.removeprefix("custom:")
            excluded_component_ids.add(int(record["id"]))
            if missing_custom_switches is not None:
                missing_custom_switches.add(switch_name)
            continue
        loadable_components.append(record)

    if sum(record.get("kind") == "jack" for record in component_records) > 1:
        raise DiagramValidationError("multiple_jacks")

    for record in wire_records:
        if not isinstance(record, dict) or not wire_fields.issubset(record):
            raise DiagramValidationError("invalid_diagram")
        if record["color"] not in WIRE_COLORS or not isinstance(record["nodes"], list):
            raise DiagramValidationError("invalid_diagram")

    excluded_wire_ids: set[int] = set()
    changed = True
    while changed:
        changed = False
        for record in wire_records:
            wire_id = int(record["id"])
            if wire_id in excluded_wire_ids:
                continue
            for endpoint in (record["start"], record["end"]):
                if not isinstance(endpoint, dict):
                    continue
                if (
                    endpoint.get("type") == "terminal"
                    and int(endpoint.get("component_id", -1)) in excluded_component_ids
                ) or (
                    endpoint.get("type") == "wire_node"
                    and int(endpoint.get("wire_id", -1)) in excluded_wire_ids
                ):
                    excluded_wire_ids.add(wire_id)
                    changed = True
                    break

    loadable_wires = [
        record for record in wire_records
        if int(record["id"]) not in excluded_wire_ids
    ]
    return loadable_components, loadable_wires
