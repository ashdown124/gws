from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox

from .components import COMPONENT_STYLES, CanvasComponent
from .diagram_io import build_diagram, load_diagram, save_diagram
from .diagram_validation import DiagramValidationError, validate_diagram
from .editor_models import WIRE_COLORS, WIRE_NODE_RADIUS, WireConnection


class DiagramControllerMixin:
    def _copy_selected_components(self) -> None:
        if self.selected_wire is not None:
            return
        source_components = [
            component for tag, component in self.components.items()
            if tag in self.selected_tags and component.kind != "jack"
        ]
        if not source_components:
            return
        history_before = self._diagram_data()
        copied_tags: list[str] = []
        offset = self.GRID_SIZE
        for source in source_components:
            source_x, source_y = self._component_position(source)
            component = CanvasComponent(
                self.canvas,
                self.next_component_id,
                source.kind,
                self.localization.text(f"component_{source.kind}"),
                source_x + offset,
                source_y + offset,
            )
            component.properties.update(source.properties)
            component.set_custom_name(
                source.custom_name,
                self.localization.text(f"component_{source.kind}"),
            )
            component.update_visual()
            component.set_gauge_value(source.gauge_value)
            component.set_switch_position(source.switch_position)
            component.rotate(source.rotation // 90)
            desired_x, desired_y = source_x + offset, source_y + offset
            actual_x, actual_y = self._component_position(component)
            component.move(desired_x - actual_x, desired_y - actual_y)
            component.set_detail(self._component_detail(component))
            component.set_external_text_visible(self.show_component_labels.get())
            self.components[component.tag] = component
            copied_tags.append(component.tag)
            self.next_component_id += 1

        self._clear_component_selection()
        for tag in copied_tags:
            self.selected_tags.add(tag)
            self.components[tag].set_selected(True)
        self.selected_tag = copied_tags[-1]
        self._refresh_element_list()
        self._render_property_editor()
        self._commit_history("component_copy", history_before)

    def _copy_shortcut(self, event: tk.Event) -> str | None:
        focused = event.widget.focus_get() if event.widget is not None else None
        if focused is not None and focused.winfo_class() in (
            "Entry", "TEntry", "TCombobox",
        ):
            return None
        self._copy_selected_components()
        return "break"

    def delete_selected(self) -> None:
        if self._delete_selected_wire_node():
            return
        history_before = self._diagram_data()
        if self.selected_wire is not None:
            deleted_wire = self.selected_wire
            self._remove_wire_cascade(deleted_wire)
            self._refresh_element_list()
            self._render_property_editor()
            self._commit_history("wire_delete", history_before)
            return
        selected_components = [
            tag for tag in self.selected_tags if tag in self.components
        ]
        if selected_components:
            if (
                self.wire_start_endpoint is not None
                and self._terminal_component_tag(self.wire_start_endpoint)
                in selected_components
            ):
                self._cancel_wire()
            for deleted_tag in selected_components:
                self._delete_connections_for_component(deleted_tag)
                self.components.pop(deleted_tag).delete()
            self.selected_tags.clear()
            self.selected_tag = None
            self._refresh_element_list()
            self._render_property_editor()
            self._commit_history("component_delete", history_before)

    def clear_canvas(self) -> None:
        self._cancel_wire()
        for wire in self.wires:
            self._delete_wire(wire)
        self.wires.clear()
        self.selected_wire = None
        self.selected_wire_node = None
        for component in self.components.values():
            component.delete()
        self.components.clear()
        self.selected_tags.clear()
        self.selected_tag = None
        self.next_component_id = 1
        self.next_wire_id = 1
        self._refresh_element_list()
        self._render_property_editor()

    def _component_position(self, component: CanvasComponent) -> tuple[float, float]:
        if component.hitbox_bounds is not None:
            x1, y1, x2, y2 = component.hitbox_bounds
            return (x1 + x2) / 2, (y1 + y2) / 2
        bounds = self.canvas.bbox(component.tag)
        if bounds is None:
            return 0.0, 0.0
        return (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

    def _endpoint_reference(self, endpoint: int) -> dict[str, int | str]:
        for component in self.components.values():
            for terminal_name, terminal_item in component.terminals.items():
                if terminal_item == endpoint:
                    return {
                        "type": "terminal",
                        "component_id": component.component_id,
                        "terminal": terminal_name,
                    }
        for wire in self.wires:
            for node_index, node_item in enumerate(wire.node_items):
                if node_item == endpoint:
                    return {"type": "wire_node", "wire_id": wire.wire_id, "node": node_index}
        raise ValueError(f"Unknown wire endpoint: {endpoint}")

    def _diagram_data(self) -> dict[str, object]:
        components = []
        for component in self.components.values():
            x, y = self._component_position(component)
            components.append({
                "id": component.component_id,
                "kind": component.kind,
                "name": component.custom_name,
                "x": x,
                "y": y,
                "properties": dict(component.properties),
                "gauge_value": component.gauge_value,
                "switch_position": component.switch_position,
                "rotation": component.rotation,
            })
        wires = [{
            "id": wire.wire_id,
            "color": wire.color,
            "start": self._endpoint_reference(wire.start_endpoint),
            "end": self._endpoint_reference(wire.end_endpoint),
            "nodes": [[x, y] for x, y in wire.nodes],
        } for wire in self.wires]
        return build_diagram(components, wires)

    def _save_diagram(self) -> None:
        path_value = filedialog.asksaveasfilename(
            parent=self.root,
            title=self.localization.text("save_diagram"),
            initialfile="diagram.gws",
            defaultextension=".gws",
            filetypes=[
                (self.localization.text("diagram_file_type"), "*.gws"),
                (self.localization.text("all_files"), "*.*"),
            ],
        )
        if not path_value:
            return
        try:
            save_diagram(path_value, self._diagram_data())
        except (OSError, ValueError) as error:
            messagebox.showerror(
                self.localization.text("save_error_title"),
                self.localization.text("save_error_message").format(error=error),
                parent=self.root,
            )
            return
        self._mark_diagram_clean(path_value)

    def _save_shortcut(self, _event: tk.Event) -> str:
        self._save_diagram()
        return "break"

    def _resolve_endpoint_reference(
        self,
        reference: dict[str, object],
        components_by_id: dict[int, CanvasComponent],
        wires_by_id: dict[int, WireConnection],
    ) -> int | None:
        if reference.get("type") == "terminal":
            component = components_by_id.get(int(reference["component_id"]))
            return None if component is None else component.terminals.get(str(reference["terminal"]))
        if reference.get("type") == "wire_node":
            wire = wires_by_id.get(int(reference["wire_id"]))
            node_index = int(reference["node"])
            if wire is not None and 0 <= node_index < len(wire.node_items):
                return wire.node_items[node_index]
        return None

    def _create_loaded_wire(
        self, wire_id: int, start: int, end: int,
        nodes: list[tuple[float, float]], color: str,
    ) -> WireConnection:
        points = self._wire_points(start, nodes, self._endpoint_center(end))
        display_color = WIRE_COLORS.get(color, WIRE_COLORS["blue"])
        highlight = self.canvas.create_line(
            *points, fill="#f59e0b", width=9, joinstyle="round",
            state="hidden", tags=("wire", "wire_highlight"),
        )
        line = self.canvas.create_line(
            *points, fill=display_color, width=3, joinstyle="round", tags=("wire",),
        )
        node_items = [self.canvas.create_oval(
            x - WIRE_NODE_RADIUS, y - WIRE_NODE_RADIUS,
            x + WIRE_NODE_RADIUS, y + WIRE_NODE_RADIUS,
            fill=display_color, outline="#ffffff", width=1, tags=("wire", "wire_node"),
        ) for x, y in nodes]
        return WireConnection(wire_id, highlight, line, start, end, nodes, node_items, color)

    def _restore_diagram(self, data: dict[str, object]) -> set[str]:
        missing_custom_switches: set[str] = set()
        try:
            component_records, wire_records = validate_diagram(
                data, self.custom_switches, missing_custom_switches
            )
        except DiagramValidationError as error:
            raise ValueError(self.localization.text(error.message_key)) from error

        self.clear_canvas()
        components_by_id: dict[int, CanvasComponent] = {}
        for record in component_records:
            if not isinstance(record, dict):
                raise ValueError(self.localization.text("invalid_diagram"))
            component_id = int(record["id"])
            kind = str(record["kind"])
            if kind not in COMPONENT_STYLES or component_id in components_by_id:
                raise ValueError(self.localization.text("invalid_diagram"))
            component = CanvasComponent(
                self.canvas, component_id, kind,
                self.localization.text(f"component_{kind}"),
                float(record["x"]), float(record["y"]),
            )
            properties = record["properties"]
            for key in component.properties:
                component.properties[key] = str(properties[key])
            component.update_visual()
            component.set_gauge_value(int(record["gauge_value"]))
            component.set_switch_position(int(record["switch_position"]))
            component.rotate(int(record.get("rotation", 0)) // 90)
            component.set_custom_name(
                str(record.get("name", "")),
                self.localization.text(f"component_{kind}"),
            )
            desired_x, desired_y = float(record["x"]), float(record["y"])
            actual_x, actual_y = self._component_position(component)
            component.move(desired_x - actual_x, desired_y - actual_y)
            component.set_detail(self._component_detail(component))
            component.set_external_text_visible(self.show_component_labels.get())
            self.components[component.tag] = component
            components_by_id[component_id] = component

        wires_by_id: dict[int, WireConnection] = {}
        pending = list(wire_records)
        while pending:
            remaining = []
            progress = False
            for record in pending:
                if not isinstance(record, dict):
                    raise ValueError(self.localization.text("invalid_diagram"))
                start_ref, end_ref = record["start"], record["end"]
                if not isinstance(start_ref, dict) or not isinstance(end_ref, dict):
                    raise ValueError(self.localization.text("invalid_diagram"))
                start = self._resolve_endpoint_reference(start_ref, components_by_id, wires_by_id)
                end = self._resolve_endpoint_reference(end_ref, components_by_id, wires_by_id)
                if start is None or end is None:
                    remaining.append(record)
                    continue
                wire_id = int(record["id"])
                if wire_id in wires_by_id:
                    raise ValueError(self.localization.text("invalid_diagram"))
                raw_nodes = record["nodes"]
                if not isinstance(raw_nodes, list):
                    raise ValueError(self.localization.text("invalid_diagram"))
                nodes = [(float(node[0]), float(node[1])) for node in raw_nodes]
                color = str(record["color"])
                wire = self._create_loaded_wire(wire_id, start, end, nodes, color)
                self.wires.append(wire)
                wires_by_id[wire_id] = wire
                progress = True
            if not progress:
                raise ValueError(self.localization.text("invalid_wire_reference"))
            pending = remaining

        self.next_component_id = max(components_by_id, default=0) + 1
        self.next_wire_id = max(wires_by_id, default=0) + 1
        self._raise_wires_above_components()
        self._refresh_element_list()
        self._render_property_editor()
        return missing_custom_switches

    def _load_diagram(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.localization.text("load_diagram"),
            filetypes=[
                (self.localization.text("diagram_file_type"), "*.gws"),
                (self.localization.text("all_files"), "*.*"),
            ],
        )
        if not path:
            return
        if not self._confirm_discard_unsaved():
            return
        try:
            data = load_diagram(path)
            missing_custom_switches = self._restore_diagram(data)
            self._reset_history()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            messagebox.showerror(
                self.localization.text("load_error_title"),
                self.localization.text("load_error_message").format(error=error),
                parent=self.root,
            )
            return
        if missing_custom_switches:
            messagebox.showwarning(
                self.localization.text("missing_custom_switch_title"),
                self.localization.text("missing_custom_switch_load_message").format(
                    names="\n".join(
                        f"- {name}" for name in sorted(missing_custom_switches)
                    )
                ),
                parent=self.root,
            )
        self._mark_diagram_clean(path)

    def _load_shortcut(self, _event: tk.Event) -> str:
        self._load_diagram()
        return "break"

    def _confirm_clear_canvas(self) -> None:
        if not self.components and not self.wires:
            return
        if messagebox.askyesno(
            self.localization.text("clear_confirm_title"),
            self.localization.text("clear_confirm_message"),
            parent=self.root,
        ):
            history_before = self._diagram_data()
            self.clear_canvas()
            self._commit_history("clear_all", history_before)

    def _clear_shortcut(self, _event: tk.Event) -> str:
        self._confirm_clear_canvas()
        return "break"
