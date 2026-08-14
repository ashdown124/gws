from __future__ import annotations

import tkinter as tk

from .components import CanvasComponent
from .editor_models import WireConnection


class CanvasSceneMixin:
    """Canvas bindings, grid, component creation, and hit testing."""

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", self._draw_grid)
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda _event: self._adjust_selected_control(1))
        self.canvas.bind("<Button-5>", lambda _event: self._adjust_selected_control(-1))
        self.root.bind("<Delete>", lambda _event: self.delete_selected())
        self.root.bind("<Control-z>", self._undo_shortcut)
        self.root.bind("<Control-y>", self._redo_shortcut)
        self.root.bind("<Control-s>", self._save_shortcut)
        self.root.bind("<Control-l>", self._load_shortcut)
        self.root.bind("<Control-n>", self._clear_shortcut)
        self.root.bind("<Control-c>", self._copy_shortcut)
        self.root.bind("<Control-a>", self._select_all_shortcut)
        self.root.bind("<Control-r>", self._rotate_clockwise_shortcut)
        self.root.bind("<Control-e>", self._rotate_counterclockwise_shortcut)
        self.root.bind("<Escape>", self._escape_shortcut)

    def _draw_grid(self, _event: tk.Event | None = None) -> None:
        self.canvas.delete("grid")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        for x in range(0, width, self.GRID_SIZE):
            self.canvas.create_line(x, 0, x, height, fill="#e1e6ed", tags="grid")
        for y in range(0, height, self.GRID_SIZE):
            self.canvas.create_line(0, y, width, y, fill="#e1e6ed", tags="grid")
        self.canvas.tag_lower("grid")
        self.canvas.coords(self.wire_mode_indicator, width - 16, height - 16)
        self.canvas.tag_raise("ui_overlay")

    def add_component(self, kind: str) -> None:
        if kind == "jack" and any(
            component.kind == "jack" for component in self.components.values()
        ):
            return
        before = self._diagram_data()
        offset = ((self.next_component_id - 1) % 5) * 18
        x = max(100, self.canvas.winfo_width() / 2 + offset)
        y = max(80, self.canvas.winfo_height() / 2 + offset)
        component = CanvasComponent(self.canvas, self.next_component_id, kind,
            self.localization.text(f"component_{kind}"), x, y)
        component.set_detail(self._component_detail(component))
        component.set_external_text_visible(self.show_component_labels.get())
        self.components[component.tag] = component
        self.next_component_id += 1
        self._select(component.tag)
        self._refresh_element_list()
        self._commit_history("component_add", before)

    def _update_add_component_button_state(self) -> None:
        jack_exists = any(
            component.kind == "jack" for component in self.components.values()
        )
        disabled = self.selected_component_kind == "jack" and jack_exists
        self.add_component_button.configure(state="disabled" if disabled else "normal")

    def _toggle_component_labels(self) -> None:
        for component in self.components.values():
            component.set_external_text_visible(self.show_component_labels.get())

    def _component_tag_at(self, x, y):
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            for tag in self.canvas.gettags(item):
                if tag in self.components:
                    return tag
        return next((tag for tag in reversed(self.components)
                     if self.components[tag].contains_point(x, y)), None)

    def _terminal_at(self, x, y):
        return next((item for item in reversed(self.canvas.find_overlapping(x, y, x, y))
                     if "terminal" in self.canvas.gettags(item)), None)

    def _wire_item_at(self, x, y):
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            tags = self.canvas.gettags(item)
            if "wire" in tags and "wire_preview" not in tags:
                return item
        for wire in reversed(self.wires):
            coordinates = self.canvas.coords(wire.line_id)
            points = list(zip(coordinates[::2], coordinates[1::2]))
            if any(self._point_segment_distance_squared(x, y, a, b) <= 36
                   for a, b in zip(points, points[1:])):
                return wire.line_id
        return None

    def _wire_node_at(self, x, y):
        return next((item for item in reversed(self.canvas.find_overlapping(x, y, x, y))
                     if "wire_node" in self.canvas.gettags(item)
                     and "wire_preview" not in self.canvas.gettags(item)), None)

    @staticmethod
    def _point_segment_distance_squared(x, y, start, end):
        x1, y1 = start; x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return (x - x1) ** 2 + (y - y1) ** 2
        ratio = max(0.0, min(1.0, ((x-x1)*dx + (y-y1)*dy) / (dx*dx + dy*dy)))
        return (x - (x1 + ratio*dx)) ** 2 + (y - (y1 + ratio*dy)) ** 2

    def _wire_for_item(self, item: int) -> WireConnection | None:
        return next((wire for wire in self.wires
                     if item in (wire.line_id, wire.highlight_id, *wire.node_items)), None)

    def _terminal_component_tag(self, terminal):
        return next((tag for tag in self.canvas.gettags(terminal) if tag in self.components), None)

    def _endpoint_center(self, endpoint):
        x1, y1, x2, y2 = self.canvas.coords(endpoint)
        return (x1+x2)/2, (y1+y2)/2

    def _terminal_center(self, terminal):
        return self._endpoint_center(terminal)
