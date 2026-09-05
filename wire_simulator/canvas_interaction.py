from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog

from .editor_models import WIRE_COLORS


class CanvasInteractionMixin:
    def _on_canvas_pan_start(self, event: tk.Event) -> str:
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _on_canvas_pan_drag(self, event: tk.Event) -> str:
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self._draw_grid()
        return "break"

    def _on_canvas_pan_end(self, _event: tk.Event) -> str:
        self.canvas.configure(
            cursor="crosshair" if self.draft_wire_start_canvas_id is not None else "arrow"
        )
        return "break"

    def _rename_component(self, component_tag: str) -> None:
        component = self.components.get(component_tag)
        if component is None:
            return
        new_name = simpledialog.askstring(
            self.localization.text("rename_component_title"),
            self.localization.text("rename_component_prompt"),
            initialvalue=component.custom_name,
            parent=self.root,
        )
        if new_name is None or new_name.strip() == component.custom_name:
            return
        history_before = self._build_diagram_snapshot()
        component.set_custom_name(
            new_name, self.localization.text(f"component_{component.kind}")
        )
        self._refresh_component_wire_panel()
        self._render_property_editor()
        self._commit_history("component_rename", history_before)

    def _rotate_selection_shortcut(self, event: tk.Event, quarter_turns: int) -> str | None:
        if self._shortcut_uses_text_editor(event):
            return None
        if self.active_component_tag not in self.components or not self.selected_component_tags:
            return "break"
        history_before = self._build_diagram_snapshot()
        self._rotate_selection(self.active_component_tag, quarter_turns)
        self._commit_history("component_rotate", history_before)
        return "break"

    def _rotate_clockwise_shortcut(self, event: tk.Event) -> str | None:
        return self._rotate_selection_shortcut(event, 1)

    def _rotate_counterclockwise_shortcut(self, event: tk.Event) -> str | None:
        return self._rotate_selection_shortcut(event, -1)

    def _on_mouse_down(self, event: tk.Event) -> None:
        self._use_canvas_event_coordinates(event)
        # Return keyboard shortcuts to the editor after a palette or property
        # widget had focus. An empty-canvas click will also clear selection
        # through the normal hit-test path below.
        self.canvas.focus_set()
        for item in reversed(self.canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            tags = self.canvas.gettags(item)
            if "rename_control" not in tags:
                continue
            component_tag = next((tag for tag in tags if tag in self.components), None)
            if component_tag is not None:
                self._rename_component(component_tag)
            return
        for item in reversed(self.canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            tags = self.canvas.gettags(item)
            if "rotation_control" not in tags:
                continue
            component_tag = next((tag for tag in tags if tag in self.components), None)
            if component_tag is not None:
                history_before = self._build_diagram_snapshot()
                self._rotate_selection(
                    component_tag, -1 if "rotate_ccw" in tags else 1
                )
                self._commit_history("component_rotate", history_before)
            return
        terminal = self._terminal_at(event.x, event.y)
        if terminal is not None:
            component_tag = self._terminal_component_tag(terminal)
            if self.draft_wire_start_canvas_id is None:
                self._select_component(component_tag)
                self._start_wire(terminal, event.x, event.y)
            elif terminal != self.draft_wire_start_canvas_id:
                self._finish_wire(terminal)
            return
        existing_node = self._wire_node_at(event.x, event.y)
        if self.draft_wire_start_canvas_id is not None:
            if existing_node is not None:
                if existing_node != self.draft_wire_start_canvas_id:
                    self._finish_wire(existing_node)
                return
            self.draft_wire_node_positions.append((event.x, event.y))
            self.draft_wire_cursor_position = (event.x, event.y)
            self._redraw_wire_preview()
            return
        if existing_node is not None:
            wire = self._wire_for_item(existing_node)
            if wire is not None:
                is_second_click = self.selected_wire_node_ref == (wire, existing_node)
                self._select_wire_node(wire, existing_node)
                self.dragged_wire_node_ref = (
                    wire, wire.node_canvas_ids.index(existing_node)
                )
                self.pending_wire_start_node_canvas_id = existing_node if is_second_click else None
                self.node_drag_started = False
                self.drag_origin = (event.x, event.y)
                self.drag_history_before = self._build_diagram_snapshot()
                return
        wire_item = self._wire_item_at(event.x, event.y)
        if wire_item is not None:
            wire = self._wire_for_item(wire_item)
            if wire is not None:
                self._select_wire(wire)
                if wire_item in wire.node_canvas_ids:
                    self.dragged_wire_node_ref = (
                        wire, wire.node_canvas_ids.index(wire_item)
                    )
                    self.pending_wire_start_node_canvas_id = wire_item
                    self.node_drag_started = False
                    self.drag_origin = (event.x, event.y)
                    self.drag_history_before = self._build_diagram_snapshot()
                return
        tag = self._component_tag_at(event.x, event.y)
        if tag is not None and event.state & 0x0004:
            self._toggle_component_selection(tag)
            self.drag_origin = None
            self.drag_history_before = None
            self.canvas.configure(cursor="arrow")
            return
        if tag not in self.selected_component_tags:
            self._select_component(tag)
        self.drag_origin = (event.x, event.y) if tag else None
        self.drag_history_before = self._build_diagram_snapshot() if tag else None
        self.canvas.configure(cursor="fleur" if tag else "arrow")

    def _on_double_click(self, event: tk.Event) -> str:
        self._use_canvas_event_coordinates(event)
        if self.draft_wire_start_canvas_id is not None or self._wire_node_at(event.x, event.y) is not None:
            return "break"
        wire_item = self._wire_item_at(event.x, event.y)
        wire = self._wire_for_item(wire_item) if wire_item is not None else None
        if wire is None:
            return "break"
        points = [
            self._endpoint_center(wire.start_endpoint_canvas_id),
            *wire.node_positions,
            self._endpoint_center(wire.end_endpoint_canvas_id),
        ]
        best_segment: tuple[float, int, float, float] | None = None
        for index, ((x1, y1), (x2, y2)) in enumerate(zip(points, points[1:])):
            dx, dy = x2 - x1, y2 - y1
            denominator = dx * dx + dy * dy
            ratio = 0.0 if denominator == 0 else max(
                0.0, min(1.0, ((event.x - x1) * dx + (event.y - y1) * dy) / denominator)
            )
            x, y = x1 + ratio * dx, y1 + ratio * dy
            distance = (event.x - x) ** 2 + (event.y - y) ** 2
            candidate = (distance, index, x, y)
            if best_segment is None or candidate < best_segment:
                best_segment = candidate
        if best_segment is None:
            return "break"
        history_before = self._build_diagram_snapshot()
        _distance, index, x, y = best_segment
        color = WIRE_COLORS.get(wire.color, WIRE_COLORS["blue"])
        node_radius = self._wire_node_display_radius()
        node_canvas_id = self.canvas.create_oval(
            x - node_radius, y - node_radius,
            x + node_radius, y + node_radius,
            fill=color, outline="#ffffff", width=self._scaled_canvas_size(1),
            tags=("wire", "wire_node"),
        )
        wire.node_positions.insert(index, (x, y))
        wire.node_canvas_ids.insert(index, node_canvas_id)
        self._update_wire_geometry(wire)
        self._select_wire_node(wire, node_canvas_id)
        self._raise_wires_above_components()
        self._refresh_component_wire_panel()
        self._commit_history("wire_node_add", history_before)
        return "break"

    def _on_mouse_drag(self, event: tk.Event) -> None:
        self._use_canvas_event_coordinates(event)
        if self.draft_wire_start_canvas_id is not None:
            return
        if self.dragged_wire_node_ref is not None:
            wire, node_index = self.dragged_wire_node_ref
            if self.drag_origin is not None and not self.node_drag_started:
                dx = event.x - self.drag_origin[0]
                dy = event.y - self.drag_origin[1]
                if dx * dx + dy * dy < 16:
                    return
                self.node_drag_started = True
                self.pending_wire_start_node_canvas_id = None
                self.canvas.configure(cursor="fleur")
            wire.node_positions[node_index] = (event.x, event.y)
            node_canvas_id = wire.node_canvas_ids[node_index]
            node_radius = self._wire_node_display_radius()
            self.canvas.coords(
                node_canvas_id,
                event.x - node_radius, event.y - node_radius,
                event.x + node_radius, event.y + node_radius,
            )
            self._update_all_wire_geometry()
            self.drag_origin = (event.x, event.y)
            return
        if not self.active_component_tag or not self.drag_origin:
            return
        old_x, old_y = self.drag_origin
        dx, dy = event.x - old_x, event.y - old_y
        for tag in list(self.selected_component_tags):
            if tag in self.components:
                self.components[tag].move(dx, dy)
        if len(self.selected_component_tags) > 1:
            self._move_wire_node_positions(
                self._connected_wires_for_selected_components(), dx, dy
            )
        self._update_all_wire_geometry()
        self.drag_origin = (event.x, event.y)

    def _on_mouse_up(self, _event: tk.Event) -> None:
        pending_node = self.pending_wire_start_node_canvas_id
        history_before = self.drag_history_before
        history_action = "wire_node_move" if self.node_drag_started else "component_move"
        self.dragged_wire_node_ref = None
        self.pending_wire_start_node_canvas_id = None
        self.node_drag_started = False
        self.drag_origin = None
        self.drag_history_before = None
        if self.draft_wire_start_canvas_id is None:
            self.canvas.configure(cursor="arrow")
        if pending_node is not None:
            x, y = self._endpoint_center(pending_node)
            self._start_wire(pending_node, x, y)
        if history_before is not None:
            self._commit_history(history_action, history_before)

    def _on_mouse_wheel(self, event: tk.Event) -> str | None:
        if event.state & 0x0004:
            pivot_x = self.canvas.canvasx(event.x)
            pivot_y = self.canvas.canvasy(event.y)
            direction = 1 if event.delta > 0 else -1
            self._set_canvas_zoom(
                self.canvas_zoom + direction * self.CANVAS_ZOOM_STEP,
                pivot_x, pivot_y,
            )
            return "break"
        if self.active_component_tag not in self.components:
            return None
        component = self.components[self.active_component_tag]
        if component.kind not in ("potentiometer", "switch"):
            return None
        direction = 1 if event.delta > 0 else -1
        self._adjust_selected_control(direction)
        return "break"

    def _on_linux_mouse_wheel(self, event: tk.Event, direction: int) -> str:
        if event.state & 0x0004:
            self._set_canvas_zoom(
                self.canvas_zoom + direction * self.CANVAS_ZOOM_STEP,
                self.canvas.canvasx(event.x), self.canvas.canvasy(event.y),
            )
        else:
            self._adjust_selected_control(direction)
        return "break"

    def _adjust_selected_control(self, direction: int) -> None:
        if self.active_component_tag not in self.components:
            return
        component = self.components[self.active_component_tag]
        if component.kind == "potentiometer":
            self._adjust_selected_potentiometer(direction * 5)
        elif component.kind == "switch":
            component.set_switch_position(component.switch_position + direction)
            component.set_detail(self._component_detail(component))
            self._refresh_component_wire_panel()

    def _adjust_selected_potentiometer(self, amount: int) -> None:
        if self.active_component_tag not in self.components:
            return
        component = self.components[self.active_component_tag]
        if component.kind == "potentiometer":
            component.set_gauge_value(component.gauge_value + amount)
            self._refresh_document_state()

    def _on_mouse_motion(self, event: tk.Event) -> None:
        self._use_canvas_event_coordinates(event)
        if self.draft_wire_start_canvas_id is None:
            return
        self.draft_wire_cursor_position = (event.x, event.y)
        self._redraw_wire_preview()

    def _on_right_click(self, event: tk.Event) -> None:
        self._use_canvas_event_coordinates(event)
        if self.draft_wire_start_canvas_id is None:
            return
        if self.draft_wire_node_positions:
            self.draft_wire_node_positions.pop()
            self.draft_wire_cursor_position = (event.x, event.y)
            self._redraw_wire_preview()
        else:
            self._cancel_wire()
