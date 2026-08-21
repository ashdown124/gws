from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


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
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as diagram_file:
            temporary_path = Path(diagram_file.name)
            json.dump(data, diagram_file, ensure_ascii=False, indent=2)
            diagram_file.flush()
            os.fsync(diagram_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_diagram(path_value: str) -> dict[str, object]:
    with Path(path_value).open("r", encoding="utf-8") as diagram_file:
        data = json.load(diagram_file)
    if not isinstance(data, dict):
        raise ValueError("Diagram root must be an object")
    return data
