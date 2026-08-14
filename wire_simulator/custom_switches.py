from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class CustomSwitchTerminal:
    terminal_id: str
    column: int
    row: int


@dataclass(frozen=True)
class CustomSwitchPosition:
    name: str
    connections: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class CustomSwitchDefinition:
    switch_id: str
    name: str
    columns: int
    rows: int
    terminals: tuple[CustomSwitchTerminal, ...]
    positions: tuple[CustomSwitchPosition, ...]
    source_path: Path


@dataclass(frozen=True)
class CustomSwitchLoadError:
    source_path: Path
    message: str


def custom_switch_directory() -> Path:
    if getattr(sys, "frozen", False):
        application_directory = Path(sys.executable).resolve().parent
    else:
        application_directory = Path(__file__).resolve().parent.parent
    return application_directory / "custom_switch"


def load_custom_switches(
    directory: Path | None = None,
    errors: list[CustomSwitchLoadError] | None = None,
) -> dict[str, CustomSwitchDefinition]:
    definition_directory = directory or custom_switch_directory()
    definition_directory.mkdir(parents=True, exist_ok=True)
    definitions: dict[str, CustomSwitchDefinition] = {}
    for path in sorted(definition_directory.glob("*.gcs")):
        try:
            definition = _load_definition(path)
        except (OSError, UnicodeError, ValueError) as error:
            if errors is not None:
                message = str(error)
                filename_prefix = f"{path.name}: "
                if message.startswith(filename_prefix):
                    message = message.removeprefix(filename_prefix)
                errors.append(CustomSwitchLoadError(path, message))
            continue
        if definition.switch_id in definitions:
            if errors is not None:
                errors.append(CustomSwitchLoadError(
                    path, f"Duplicate custom switch name: {definition.name}"
                ))
            continue
        definitions[definition.switch_id] = definition
    return definitions


def _load_definition(path: Path) -> CustomSwitchDefinition:
    with path.open("r", encoding="utf-8") as definition_file:
        source = definition_file.read()

    section_match = re.fullmatch(
        r"\s*\[Name\]\s*\r?\n"
        r"(?P<name>[^\r\n]+)\s*\r?\n"
        r"\[Grid\]\s*\r?\n"
        r"(?P<columns>\d+)\s+(?P<rows>\d+)\s*\r?\n"
        r"\[Position\](?P<positions>.*)",
        source,
        re.DOTALL,
    )
    if section_match is None:
        raise ValueError(
            f"{path.name}: expected [Name], [Grid], and [Position] sections"
        )

    name = section_match.group("name").strip()
    if not name:
        raise ValueError(f"{path.name}: name is required")
    switch_id = name

    columns = int(section_match.group("columns"))
    rows = int(section_match.group("rows"))
    if not 1 <= columns <= 12 or not 1 <= rows <= 12 or columns * rows < 2:
        raise ValueError(f"{path.name}: terminal grid must contain 2-144 terminals")

    terminals = tuple(
        CustomSwitchTerminal(str(row * columns + column), column, row)
        for row in range(rows)
        for column in range(columns)
    )
    terminal_ids = {terminal.terminal_id for terminal in terminals}

    position_source = section_match.group("positions")
    record_pattern = re.compile(r'\s*"(?P<name>[^"\r\n]+)"\s*(?P<body>[^;]*);')
    pair_pattern = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
    connection_list_pattern = re.compile(
        r"\s*(?:\(\s*\d+\s*,\s*\d+\s*\)"
        r"(?:\s*,\s*\(\s*\d+\s*,\s*\d+\s*\))*)?\s*"
    )
    positions: list[CustomSwitchPosition] = []
    position_names: set[str] = set()
    cursor = 0
    for record in record_pattern.finditer(position_source):
        if position_source[cursor:record.start()].strip():
            raise ValueError(f"{path.name}: invalid position syntax")
        cursor = record.end()
        position_name = record.group("name").strip()
        if not position_name or position_name in position_names:
            raise ValueError(f"{path.name}: invalid or duplicate position")
        position_names.add(position_name)

        body = record.group("body")
        if connection_list_pattern.fullmatch(body) is None:
            raise ValueError(f"{path.name}: connections must use the '(n,m)' format")
        pair_matches = list(pair_pattern.finditer(body))
        connections: list[tuple[str, ...]] = []
        used_in_position: set[str] = set()
        for pair_match in pair_matches:
            pair = (pair_match.group(1), pair_match.group(2))
            if (pair[0] == pair[1] or not set(pair) <= terminal_ids
                    or used_in_position & set(pair)):
                raise ValueError(f"{path.name}: invalid or overlapping terminal pair")
            used_in_position.update(pair)
            connections.append(pair)
        positions.append(CustomSwitchPosition(position_name, tuple(connections)))

    if position_source[cursor:].strip():
        raise ValueError(f"{path.name}: each position must end with ';'")
    if not positions:
        raise ValueError(f"{path.name}: at least one position is required")
    return CustomSwitchDefinition(
        switch_id, name, columns, rows, terminals, tuple(positions), path
    )
