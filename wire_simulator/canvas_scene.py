from __future__ import annotations

import math
import tkinter as tk

from .components import CanvasComponent
from .editor_models import WIRE_NODE_RADIUS, WireConnection


class CanvasSceneMixin:
    """Canvas bindings, grid, component creation, and hit testing."""

    SHORTCUT_BINDTAG = "GwsApplicationShortcuts"
    CANVAS_EXTENT = 100_000
    MIN_CANVAS_ZOOM = 0.5
    MAX_CANVAS_ZOOM = 1.0
    CANVAS_ZOOM_STEP = 0.1

    @staticmethod
    def _rounded_scaled_size(base_size: float, scale: float) -> int:
        return max(1, math.floor(base_size * scale + 0.5))

    def _scaled_canvas_size(self, base_size: float) -> int:
        return self._rounded_scaled_size(base_size, self.canvas_zoom)

    def _wire_node_display_radius(self) -> int:
        return self._scaled_canvas_size(WIRE_NODE_RADIUS)

    def _apply_wire_stroke_scale(self) -> None:
        for wire in self.wires:
            self.canvas.itemconfigure(
                wire.line_canvas_id, width=self._scaled_canvas_size(3)
            )
            self.canvas.itemconfigure(
                wire.highlight_canvas_id, width=self._scaled_canvas_size(9)
            )
            for node_canvas_id in wire.node_canvas_ids:
                selected = (
                    getattr(self, "selected_wire_node_ref", None) is not None
                    and self.selected_wire_node_ref[1] == node_canvas_id
                )
                self.canvas.itemconfigure(
                    node_canvas_id,
                    width=self._scaled_canvas_size(3 if selected else 1),
                )

    def _update_canvas_zoom_label(self) -> None:
        if hasattr(self, "canvas_zoom_label"):
            self.canvas_zoom_label.configure(text=f"{round(self.canvas_zoom * 100):d}%")

    def _diagram_to_canvas_point(self, x: float, y: float) -> tuple[float, float]:
        return (
            x * self.canvas_zoom + self.canvas_zoom_offset_x,
            y * self.canvas_zoom + self.canvas_zoom_offset_y,
        )

    def _canvas_to_diagram_point(self, x: float, y: float) -> tuple[float, float]:
        return (
            (x - self.canvas_zoom_offset_x) / self.canvas_zoom,
            (y - self.canvas_zoom_offset_y) / self.canvas_zoom,
        )

    def _set_canvas_zoom(self, target_zoom: float, pivot_x: float, pivot_y: float) -> None:
        target_zoom = max(self.MIN_CANVAS_ZOOM, min(self.MAX_CANVAS_ZOOM, target_zoom))
        target_zoom = round(target_zoom, 1)
        if target_zoom == self.canvas_zoom:
            return
        factor = target_zoom / self.canvas_zoom
        for component in self.components.values():
            component.scale_for_view(factor, pivot_x, pivot_y, target_zoom)
        target_node_radius = self._rounded_scaled_size(WIRE_NODE_RADIUS, target_zoom)
        for wire in self.wires:
            wire.node_positions = [
                (
                    pivot_x + (x - pivot_x) * factor,
                    pivot_y + (y - pivot_y) * factor,
                )
                for x, y in wire.node_positions
            ]
            for node_canvas_id, (x, y) in zip(
                wire.node_canvas_ids, wire.node_positions
            ):
                self.canvas.coords(
                    node_canvas_id,
                    x - target_node_radius, y - target_node_radius,
                    x + target_node_radius, y + target_node_radius,
                )
        self.draft_wire_node_positions = [
            (
                pivot_x + (x - pivot_x) * factor,
                pivot_y + (y - pivot_y) * factor,
            )
            for x, y in self.draft_wire_node_positions
        ]
        if self.draft_wire_cursor_position is not None:
            x, y = self.draft_wire_cursor_position
            self.draft_wire_cursor_position = (
                pivot_x + (x - pivot_x) * factor,
                pivot_y + (y - pivot_y) * factor,
            )
        self.canvas_zoom_offset_x = (
            pivot_x + (self.canvas_zoom_offset_x - pivot_x) * factor
        )
        self.canvas_zoom_offset_y = (
            pivot_y + (self.canvas_zoom_offset_y - pivot_y) * factor
        )
        self.canvas_zoom = target_zoom
        self._update_canvas_zoom_label()
        self._apply_wire_stroke_scale()
        self._update_all_wire_geometry()
        if self.draft_wire_start_canvas_id is not None:
            self._redraw_wire_preview()
        self._draw_grid()

    def _reset_canvas_zoom(self) -> None:
        if self.canvas_zoom != 1.0:
            pivot_x = self.canvas_zoom_offset_x / (1.0 - self.canvas_zoom)
            pivot_y = self.canvas_zoom_offset_y / (1.0 - self.canvas_zoom)
            self._set_canvas_zoom(1.0, pivot_x, pivot_y)
        self.canvas_zoom = 1.0
        self.canvas_zoom_offset_x = 0.0
        self.canvas_zoom_offset_y = 0.0
        self._update_canvas_zoom_label()

    def _reset_canvas_view(self) -> None:
        self.canvas.configure(
            scrollregion=(
                -self.CANVAS_EXTENT, -self.CANVAS_EXTENT,
                self.CANVAS_EXTENT, self.CANVAS_EXTENT,
            )
        )
        self.canvas.xview_moveto(0.5)
        self.canvas.yview_moveto(0.5)
        self._draw_grid()

    def _use_canvas_event_coordinates(self, event: tk.Event) -> None:
        """Convert viewport-relative event coordinates to diagram coordinates."""
        event.x = self.canvas.canvasx(event.x)
        event.y = self.canvas.canvasy(event.y)

    def _install_shortcut_bindtag(self, widget: tk.Misc) -> None:
        tags = widget.bindtags()
        if self.SHORTCUT_BINDTAG not in tags:
            widget.bindtags((self.SHORTCUT_BINDTAG, *tags))

    def _register_shortcut_widget(self, event: tk.Event) -> None:
        self._install_shortcut_bindtag(event.widget)

    def _shortcut_uses_text_editor(self, event: tk.Event) -> bool:
        focused = event.widget if event.widget is not None else self.root.focus_get()
        return focused is not None and focused.winfo_class() in (
            "Entry", "TEntry", "Text", "Spinbox", "TSpinbox",
        )

    def _route_shortcut(
        self, event: tk.Event, handler, *, preserve_text_editing: bool = False
    ) -> str | None:
        focused = event.widget if event.widget is not None else self.root.focus_get()
        if focused is not None and focused.winfo_toplevel() is not self.root:
            return None
        if preserve_text_editing and self._shortcut_uses_text_editor(event):
            return None
        return handler(event)

    def _delete_shortcut(self, _event: tk.Event) -> str:
        self.delete_selected()
        return "break"

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", self._draw_grid)
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<ButtonPress-2>", self._on_canvas_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_canvas_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_canvas_pan_end)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._on_linux_mouse_wheel(event, 1))
        self.canvas.bind("<Button-5>", lambda event: self._on_linux_mouse_wheel(event, -1))
        shortcuts = (
            ("<Delete>", self._delete_shortcut, True),
            ("<Control-z>", self._undo_shortcut, False),
            ("<Control-y>", self._redo_shortcut, False),
            ("<Control-s>", self._save_shortcut, False),
            ("<Control-l>", self._load_shortcut, False),
            ("<Control-n>", self._new_diagram_shortcut, False),
            ("<Control-c>", self._copy_shortcut, True),
            ("<Control-a>", self._select_all_shortcut, True),
            ("<Control-r>", self._rotate_clockwise_shortcut, True),
            ("<Control-e>", self._rotate_counterclockwise_shortcut, True),
            ("<Escape>", self._escape_shortcut, False),
        )
        for sequence, handler, preserve_text_editing in shortcuts:
            callback = lambda event, action=handler, preserve=preserve_text_editing: (
                self._route_shortcut(
                    event, action, preserve_text_editing=preserve
                )
            )
            self.root.bind_class(self.SHORTCUT_BINDTAG, sequence, callback)
            if sequence.startswith("<Control-"):
                uppercase_sequence = (
                    f"{sequence[:-2]}{sequence[-2].upper()}{sequence[-1]}"
                )
                self.root.bind_class(
                    self.SHORTCUT_BINDTAG, uppercase_sequence, callback
                )

        self.root.bind_all("<FocusIn>", self._register_shortcut_widget, add="+")
        pending = [self.root]
        while pending:
            widget = pending.pop()
            self._install_shortcut_bindtag(widget)
            pending.extend(widget.winfo_children())

    def _draw_grid(self, _event: tk.Event | None = None) -> None:
        self.canvas.delete("grid")
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(width)
        bottom = self.canvas.canvasy(height)
        spacing = self.GRID_SIZE * self.canvas_zoom
        first_x = (
            self.canvas_zoom_offset_x
            + math.floor((left - self.canvas_zoom_offset_x) / spacing) * spacing
        )
        first_y = (
            self.canvas_zoom_offset_y
            + math.floor((top - self.canvas_zoom_offset_y) / spacing) * spacing
        )
        x = first_x
        while x <= right + spacing:
            self.canvas.create_line(x, top, x, bottom, fill="#e1e6ed", tags="grid")
            x += spacing
        y = first_y
        while y <= bottom + spacing:
            self.canvas.create_line(left, y, right, y, fill="#e1e6ed", tags="grid")
            y += spacing
        self.canvas.tag_lower("grid")
        self.canvas.coords(
            self.wire_mode_indicator,
            self.canvas.canvasx(width - 16), self.canvas.canvasy(height - 16),
        )
        self.canvas.tag_raise("ui_overlay")

    def add_component(self, kind: str) -> None:
        if kind == "jack" and any(
            component.kind == "jack" for component in self.components.values()
        ):
            return
        before = self._build_diagram_snapshot()
        offset = ((self.next_component_id - 1) % 5) * 18
        x = self.canvas.canvasx(self.canvas.winfo_width() / 2) + offset
        y = self.canvas.canvasy(self.canvas.winfo_height() / 2) + offset
        component = CanvasComponent(self.canvas, self.next_component_id, kind,
            self.localization.text(f"component_{kind}"), x, y)
        component.set_detail(self._component_detail(component))
        component.set_external_text_visible(self.show_component_labels.get())
        component.scale_for_view(self.canvas_zoom, x, y, self.canvas_zoom)
        self.components[component.tag] = component
        self.next_component_id += 1
        self._select_component(component.tag)
        self._refresh_component_wire_panel()
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
        exact = next((
            item for item in reversed(self.canvas.find_overlapping(x, y, x, y))
            if "terminal" in self.canvas.gettags(item)
        ), None)
        if exact is not None:
            return exact
        nearest: tuple[float, int] | None = None
        for component in self.components.values():
            for item in component.terminals.values():
                if self.canvas.itemcget(item, "state") == "hidden":
                    continue
                bounds = self.canvas.coords(item)
                if len(bounds) != 4:
                    continue
                center_x = (bounds[0] + bounds[2]) / 2
                center_y = (bounds[1] + bounds[3]) / 2
                distance = (x - center_x) ** 2 + (y - center_y) ** 2
                if distance <= 81 and (nearest is None or distance < nearest[0]):
                    nearest = (distance, item)
        return None if nearest is None else nearest[1]

    def _wire_item_at(self, x, y):
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            tags = self.canvas.gettags(item)
            if "wire" in tags and "wire_preview" not in tags:
                return item
        for wire in reversed(self.wires):
            coordinates = self.canvas.coords(wire.line_canvas_id)
            points = list(zip(coordinates[::2], coordinates[1::2]))
            if any(self._point_segment_distance_squared(x, y, a, b) <= 36
                   for a, b in zip(points, points[1:])):
                return wire.line_canvas_id
        return None

    def _wire_node_at(self, x, y):
        exact = next((
            item for item in reversed(self.canvas.find_overlapping(x, y, x, y))
            if "wire_node" in self.canvas.gettags(item)
            and "wire_preview" not in self.canvas.gettags(item)
        ), None)
        if exact is not None:
            return exact
        nearest: tuple[float, int] | None = None
        for wire in self.wires:
            for item in wire.node_canvas_ids:
                bounds = self.canvas.coords(item)
                center_x = (bounds[0] + bounds[2]) / 2
                center_y = (bounds[1] + bounds[3]) / 2
                distance = (x - center_x) ** 2 + (y - center_y) ** 2
                if distance <= 81 and (nearest is None or distance < nearest[0]):
                    nearest = (distance, item)
        return None if nearest is None else nearest[1]

    @staticmethod
    def _point_segment_distance_squared(x, y, start, end):
        x1, y1 = start
        x2, y2 = end
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return (x - x1) ** 2 + (y - y1) ** 2
        ratio = max(0.0, min(1.0, ((x-x1)*dx + (y-y1)*dy) / (dx*dx + dy*dy)))
        return (x - (x1 + ratio*dx)) ** 2 + (y - (y1 + ratio*dy)) ** 2

    def _wire_for_item(self, item: int) -> WireConnection | None:
        return next((wire for wire in self.wires
                     if item in (
                         wire.line_canvas_id,
                         wire.highlight_canvas_id,
                         *wire.node_canvas_ids,
                     )), None)

    def _terminal_component_tag(self, terminal):
        return next((tag for tag in self.canvas.gettags(terminal) if tag in self.components), None)

    def _endpoint_center(self, endpoint):
        x1, y1, x2, y2 = self.canvas.coords(endpoint)
        return (x1+x2)/2, (y1+y2)/2

    def _terminal_center(self, terminal):
        return self._endpoint_center(terminal)
