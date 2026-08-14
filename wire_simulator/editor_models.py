from __future__ import annotations

from dataclasses import dataclass, field


WIRE_COLORS = {
    "blue": "#2563eb",
    "red": "#dc2626",
    "black": "#111827",
    "green": "#16a34a",
    "yellow": "#eab308",
    "gray": "#A0A0A0",
}

WIRE_NODE_RADIUS = 9


@dataclass
class WireConnection:
    wire_id: int
    highlight_id: int
    line_id: int
    start_endpoint: int
    end_endpoint: int
    nodes: list[tuple[float, float]] = field(default_factory=list)
    node_items: list[int] = field(default_factory=list)
    color: str = "blue"


@dataclass(frozen=True)
class HistoryEntry:
    action: str
    before: dict[str, object]
    after: dict[str, object]
