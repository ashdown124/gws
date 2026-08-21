from __future__ import annotations

from collections.abc import Mapping
import math

from .components import COMPONENT_PROPERTY_SCHEMAS, COMPONENT_STYLES
from .diagram_io import has_supported_envelope
from .editor_models import WIRE_COLORS


class DiagramValidationError(ValueError):
    """A diagram failed structural validation."""

    def __init__(self, message_key: str) -> None:
        super().__init__(message_key)
        self.message_key = message_key


def _invalid() -> DiagramValidationError:
    return DiagramValidationError("invalid_diagram")


def _positive_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid()
    return value


def _bounded_integer(value: object, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise _invalid()
    return value


def _finite_number(value: object) -> float:
    if isinstance(value, bool):
        raise _invalid()
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise _invalid() from error
    if not math.isfinite(number):
        raise _invalid()
    return number


def _component_terminal_names(
    kind: str, properties: dict[str, object], custom_switches: Mapping[str, object],
) -> set[str]:
    if kind == "pickup":
        if properties["pickup_type"] == "humbucker":
            return {"north_hot", "north_gnd", "south_hot", "south_gnd"}
        return {"single_hot", "single_gnd"}
    if kind == "potentiometer":
        return {"1", "2", "3"}
    if kind in ("resistor", "capacitor"):
        return {"1", "2"}
    if kind == "jack":
        return {"hot", "gnd"}
    if kind == "ground":
        return {"gnd"}
    switch_type = str(properties["switch_type"])
    if switch_type.startswith("custom:"):
        definition = custom_switches[switch_type.removeprefix("custom:")]
        return {
            f"custom_{terminal.terminal_id}"
            for terminal in getattr(definition, "terminals")
        }
    if switch_type == "toggle_3way":
        return {"toggle_A", "toggle_A_prime", "toggle_B", "toggle_B_prime"}
    return {"A0", "A1", "A2", "A3", "B0", "B1", "B2", "B3"}


def _validate_component_properties(
    kind: str, properties: dict[str, object], custom_switches: Mapping[str, object],
) -> None:
    required_properties: set[str] = set()
    for field in COMPONENT_PROPERTY_SCHEMAS.get(kind, []):
        key = str(field["key"])
        required_properties.add(key)
        if "units" in field:
            required_properties.add(f"{key}_unit")
    if set(properties) != required_properties:
        raise _invalid()

    for field in COMPONENT_PROPERTY_SCHEMAS.get(kind, []):
        key = str(field["key"])
        value = properties[key]
        if field["type"] == "choice":
            allowed = set(field["choices"])
            if kind == "switch" and str(value).startswith("custom:"):
                if str(value).removeprefix("custom:") not in custom_switches:
                    continue
            elif value not in allowed:
                raise _invalid()
        elif _finite_number(value) <= 0.0:
            raise _invalid()
        if "units" in field and properties[f"{key}_unit"] not in field["units"]:
            raise _invalid()


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

    component_fields = {
        "id", "kind", "x", "y", "properties", "gauge_value", "switch_position"
    }
    wire_fields = {"id", "color", "start", "end", "nodes"}
    loadable_components: list[dict[str, object]] = []
    excluded_component_ids: set[int] = set()
    component_ids: set[int] = set()
    terminal_names_by_component_id: dict[int, set[str]] = {}
    for record in component_records:
        if not isinstance(record, dict) or not component_fields.issubset(record):
            raise _invalid()
        if "name" in record and not isinstance(record["name"], str):
            raise _invalid()
        component_id = _positive_integer(record["id"])
        if component_id in component_ids:
            raise _invalid()
        component_ids.add(component_id)
        _finite_number(record["x"])
        _finite_number(record["y"])
        _bounded_integer(record["gauge_value"], 0, 100)
        kind = str(record["kind"])
        properties = record["properties"]
        if kind not in COMPONENT_STYLES or not isinstance(properties, dict):
            raise _invalid()
        _validate_component_properties(kind, properties, custom_switches)
        if kind == "jack" and properties.get("jack_type") != "mono":
            raise _invalid()
        rotation = record.get("rotation", 0)
        if not isinstance(rotation, int) or rotation not in (0, 90, 180, 270):
            raise _invalid()
        switch_type = str(properties.get("switch_type", ""))
        if (
            kind == "switch"
            and switch_type.startswith("custom:")
            and switch_type.removeprefix("custom:") not in custom_switches
        ):
            switch_name = switch_type.removeprefix("custom:")
            excluded_component_ids.add(component_id)
            if missing_custom_switches is not None:
                missing_custom_switches.add(switch_name)
            continue
        if kind == "switch":
            if switch_type.startswith("custom:"):
                max_position = len(
                    getattr(custom_switches[switch_type.removeprefix("custom:")], "positions")
                )
            else:
                max_position = 5 if switch_type == "blade_5way" else 3
            _bounded_integer(record["switch_position"], 1, max_position)
        else:
            _bounded_integer(record["switch_position"], 1, 1)
        terminal_names_by_component_id[component_id] = _component_terminal_names(
            kind, properties, custom_switches
        )
        loadable_components.append(record)

    if sum(record.get("kind") == "jack" for record in component_records) > 1:
        raise DiagramValidationError("multiple_jacks")

    wire_ids: set[int] = set()
    node_counts_by_wire_id: dict[int, int] = {}
    for record in wire_records:
        if not isinstance(record, dict) or not wire_fields.issubset(record):
            raise _invalid()
        wire_id = _positive_integer(record["id"])
        if wire_id in wire_ids:
            raise _invalid()
        wire_ids.add(wire_id)
        if record["color"] not in WIRE_COLORS or not isinstance(record["nodes"], list):
            raise _invalid()
        for node in record["nodes"]:
            if not isinstance(node, (list, tuple)) or len(node) != 2:
                raise _invalid()
            _finite_number(node[0])
            _finite_number(node[1])
        node_counts_by_wire_id[wire_id] = len(record["nodes"])

    def endpoint_dependency(endpoint: object) -> int | None:
        if not isinstance(endpoint, dict):
            raise _invalid()
        endpoint_type = endpoint.get("type")
        if endpoint_type == "terminal":
            component_id = _positive_integer(endpoint.get("component_id"))
            if component_id in excluded_component_ids:
                return None
            if (
                component_id not in terminal_names_by_component_id
                or endpoint.get("terminal")
                not in terminal_names_by_component_id[component_id]
            ):
                raise _invalid()
            return None
        if endpoint_type == "wire_node":
            wire_id = _positive_integer(endpoint.get("wire_id"))
            node_index = endpoint.get("node")
            if (
                wire_id not in node_counts_by_wire_id
                or isinstance(node_index, bool)
                or not isinstance(node_index, int)
                or not 0 <= node_index < node_counts_by_wire_id[wire_id]
            ):
                raise _invalid()
            return wire_id
        raise _invalid()

    excluded_wire_ids: set[int] = set()
    changed = True
    while changed:
        changed = False
        for record in wire_records:
            wire_id = int(record["id"])
            if wire_id in excluded_wire_ids:
                continue
            for endpoint in (record["start"], record["end"]):
                dependency = endpoint_dependency(endpoint)
                if (
                    endpoint.get("type") == "terminal"
                    and endpoint.get("component_id") in excluded_component_ids
                ) or (
                    dependency is not None and dependency in excluded_wire_ids
                ):
                    excluded_wire_ids.add(wire_id)
                    changed = True
                    break

    loadable_wires = [
        record for record in wire_records
        if int(record["id"]) not in excluded_wire_ids
    ]

    unresolved_wire_ids = {int(record["id"]) for record in loadable_wires}
    while unresolved_wire_ids:
        resolved_this_pass: set[int] = set()
        for record in loadable_wires:
            wire_id = int(record["id"])
            if wire_id not in unresolved_wire_ids:
                continue
            dependencies = {
                dependency
                for endpoint in (record["start"], record["end"])
                if (dependency := endpoint_dependency(endpoint)) is not None
            }
            if dependencies.isdisjoint(unresolved_wire_ids):
                resolved_this_pass.add(wire_id)
        if not resolved_this_pass:
            raise DiagramValidationError("invalid_wire_reference")
        unresolved_wire_ids.difference_update(resolved_this_pass)
    return loadable_components, loadable_wires
