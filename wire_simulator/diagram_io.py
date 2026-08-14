from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DIAGRAM_FORMAT = "guitar-wiring-simulator"
DIAGRAM_VERSION = 1


def build_diagram(
    components: list[dict[str, object]], wires: list[dict[str, object]],
) -> dict[str, object]:
    """Build the versioned document envelope used by history and .gws files."""
    return {
        "format": DIAGRAM_FORMAT,
        "version": DIAGRAM_VERSION,
        "components": components,
        "wires": wires,
    }


def has_supported_envelope(data: dict[str, object]) -> bool:
    return data.get("format") == DIAGRAM_FORMAT and data.get("version") == DIAGRAM_VERSION


def save_diagram(path_value: str, data: dict[str, object]) -> None:
    path = Path(path_value).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as diagram_file:
        json.dump(data, diagram_file, ensure_ascii=False, indent=2)


def load_diagram(path_value: str) -> dict[str, Any]:
    with Path(path_value).open("r", encoding="utf-8") as diagram_file:
        data = json.load(diagram_file)
    if not isinstance(data, dict):
        raise ValueError("Diagram root must be an object")
    return data
