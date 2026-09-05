from __future__ import annotations

from .editor_models import WireConnection


class WiringControllerMixin:
    """Wire creation, geometry, selection, and cascading deletion."""

    def _start_wire(self, start_endpoint_canvas_id, x, y):
        self._clear_wire_selection()
        self.draft_wire_start_canvas_id = start_endpoint_canvas_id
        self.draft_wire_node_positions = []
        self.draft_wire_cursor_position = (x, y)
        self.canvas.configure(cursor="crosshair")
        self.canvas.itemconfigure(self.wire_mode_indicator, state="normal")
        self.canvas.tag_raise("ui_overlay")
        self._redraw_wire_preview()
        self._update_status_bar()

    def _wire_points(self, start_endpoint_canvas_id, node_positions, end_position):
        points = [
            self._endpoint_center(start_endpoint_canvas_id),
            *node_positions,
            end_position,
        ]
        return [coordinate for point in points for coordinate in point]

    def _redraw_wire_preview(self):
        for canvas_id in self.wire_preview_canvas_ids: self.canvas.delete(canvas_id)
        self.wire_preview_canvas_ids.clear()
        if self.draft_wire_start_canvas_id is None or self.draft_wire_cursor_position is None: return
        self.wire_preview_canvas_ids.append(self.canvas.create_line(
            *self._wire_points(
                self.draft_wire_start_canvas_id,
                self.draft_wire_node_positions,
                self.draft_wire_cursor_position,
            ),
            fill="#2563eb", width=self._scaled_canvas_size(3),
            joinstyle="round", tags=("wire", "wire_preview")))
        node_radius = self._wire_node_display_radius()
        for x, y in self.draft_wire_node_positions:
            self.wire_preview_canvas_ids.append(self.canvas.create_oval(
                x-node_radius, y-node_radius,
                x+node_radius, y+node_radius,
                fill="#2563eb", outline="#ffffff",
                width=self._scaled_canvas_size(1),
                tags=("wire", "wire_preview", "wire_node")))
        self._raise_wires_above_components()

    def _finish_wire(self, end_endpoint):
        if self.draft_wire_start_canvas_id is None: return
        before = self._build_diagram_snapshot()
        start_endpoint_canvas_id = self.draft_wire_start_canvas_id
        points = self._wire_points(
            start_endpoint_canvas_id,
            self.draft_wire_node_positions,
            self._endpoint_center(end_endpoint),
        )
        highlight_canvas_id = self.canvas.create_line(
            *points, fill="#f59e0b", width=self._scaled_canvas_size(9),
            joinstyle="round", state="hidden", tags=("wire", "wire_highlight"))
        line_canvas_id = self.canvas.create_line(
            *points, fill="#2563eb", width=self._scaled_canvas_size(3),
            joinstyle="round", tags=("wire",))
        node_radius = self._wire_node_display_radius()
        node_canvas_ids = [self.canvas.create_oval(
            x-node_radius, y-node_radius,
            x+node_radius, y+node_radius, fill="#2563eb",
            outline="#ffffff", width=self._scaled_canvas_size(1),
            tags=("wire", "wire_node"))
            for x, y in self.draft_wire_node_positions
        ]
        self.wires.append(WireConnection(
            wire_id=self.next_wire_id,
            highlight_canvas_id=highlight_canvas_id,
            line_canvas_id=line_canvas_id,
            start_endpoint_canvas_id=start_endpoint_canvas_id,
            end_endpoint_canvas_id=end_endpoint,
            node_positions=list(self.draft_wire_node_positions),
            node_canvas_ids=node_canvas_ids,
        ))
        self.next_wire_id += 1
        self._cancel_wire()
        self._raise_wires_above_components()
        self._refresh_component_wire_panel()
        self._commit_history("wire_add", before)

    def _cancel_wire(self):
        for canvas_id in self.wire_preview_canvas_ids: self.canvas.delete(canvas_id)
        self.wire_preview_canvas_ids.clear()
        self.draft_wire_start_canvas_id = None
        self.draft_wire_node_positions = []
        self.draft_wire_cursor_position = None
        self.canvas.configure(cursor="arrow")
        self.canvas.itemconfigure(self.wire_mode_indicator, state="hidden")
        self._update_status_bar()

    def _raise_wires_above_components(self):
        self.canvas.tag_lower("grid")
        self.canvas.tag_raise("wire")
        self.canvas.tag_raise("ui_overlay")

    def _update_all_wire_geometry(self):
        for wire in self.wires: self._update_wire_geometry(wire)

    def _update_wire_geometry(self, wire):
        points = self._wire_points(
            wire.start_endpoint_canvas_id,
            wire.node_positions,
            self._endpoint_center(wire.end_endpoint_canvas_id),
        )
        self.canvas.coords(wire.highlight_canvas_id, *points)
        self.canvas.coords(wire.line_canvas_id, *points)

    def _delete_wire_canvas_items(self, wire):
        self.canvas.delete(wire.highlight_canvas_id)
        self.canvas.delete(wire.line_canvas_id)
        for node_canvas_id in wire.node_canvas_ids: self.canvas.delete(node_canvas_id)

    def _remove_wire_cascade(self, wire):
        if wire not in self.wires: return
        self.wires.remove(wire)
        if self.selected_wire is wire:
            self.selected_wire = None
            self.selected_wire_node_ref = None
        if self.draft_wire_start_canvas_id in wire.node_canvas_ids: self._cancel_wire()
        for child in [candidate for candidate in self.wires
                      if candidate.start_endpoint_canvas_id in wire.node_canvas_ids
                      or candidate.end_endpoint_canvas_id in wire.node_canvas_ids]:
            self._remove_wire_cascade(child)
        self._delete_wire_canvas_items(wire)

    def _select_wire(self, wire):
        self._clear_wire_selection()
        self._clear_component_selection()
        self.active_component_tag = None
        self.selected_wire = wire
        self.canvas.itemconfigure(wire.highlight_canvas_id, state="normal")
        self._sync_component_wire_list_selection()
        self._render_property_editor()
        self._raise_wires_above_components()
        self._update_status_bar()

    def _select_wire_node(self, wire, node_canvas_id):
        self._select_wire(wire)
        self.canvas.itemconfigure(wire.highlight_canvas_id, state="hidden")
        self.selected_wire_node_ref = (wire, node_canvas_id)
        self.canvas.itemconfigure(
            node_canvas_id, outline="#f59e0b", width=self._scaled_canvas_size(3)
        )

    def _clear_wire_node_selection(self):
        if self.selected_wire_node_ref is not None:
            _wire, node_canvas_id = self.selected_wire_node_ref
            if self.canvas.type(node_canvas_id):
                self.canvas.itemconfigure(
                    node_canvas_id, outline="#ffffff", width=self._scaled_canvas_size(1)
                )
        self.selected_wire_node_ref = None

    def _clear_wire_selection(self):
        self._clear_wire_node_selection()
        if self.selected_wire is not None:
            self.canvas.itemconfigure(self.selected_wire.highlight_canvas_id, state="hidden")
        self.selected_wire = None

    def _delete_selected_wire_node(self) -> bool:
        if self.selected_wire_node_ref is None:
            return False
        wire, node_canvas_id = self.selected_wire_node_ref
        if wire not in self.wires or node_canvas_id not in wire.node_canvas_ids:
            self.selected_wire_node_ref = None
            return False
        history_before = self._build_diagram_snapshot()
        node_index = wire.node_canvas_ids.index(node_canvas_id)
        for branch in list(self.wires):
            if branch is not wire and node_canvas_id in (
                branch.start_endpoint_canvas_id, branch.end_endpoint_canvas_id
            ):
                self._remove_wire_cascade(branch)
        self.canvas.delete(node_canvas_id)
        wire.node_canvas_ids.pop(node_index)
        wire.node_positions.pop(node_index)
        self.selected_wire_node_ref = None
        self.selected_wire = wire
        self._update_wire_geometry(wire)
        self.canvas.itemconfigure(wire.highlight_canvas_id, state="normal")
        self._refresh_component_wire_panel()
        self._render_property_editor()
        self._commit_history("wire_node_delete", history_before)
        return True

    def _delete_wires_for_component(self, component_tag):
        for wire in list(self.wires):
            if component_tag in (
                self._terminal_component_tag(wire.start_endpoint_canvas_id),
                self._terminal_component_tag(wire.end_endpoint_canvas_id),
            ):
                self._remove_wire_cascade(wire)

    def _clear_component_selection(self):
        for component_tag in list(self.selected_component_tags):
            if component_tag in self.components:
                self.components[component_tag].set_selected(False)
        self.selected_component_tags.clear()

    def _select_component(self, tag, additive=False):
        self._clear_wire_selection()
        if not additive:
            self._clear_component_selection()
        if tag in self.components:
            self.selected_component_tags.add(tag)
            self.active_component_tag = tag
            self.components[tag].set_selected(True)
        elif not additive:
            self.active_component_tag = None
        self._sync_component_wire_list_selection()
        self._render_property_editor()
        self._update_status_bar()

    def _toggle_component_selection(self, tag):
        self._clear_wire_selection()
        if tag not in self.components:
            return
        if tag in self.selected_component_tags:
            self.components[tag].set_selected(False)
            self.selected_component_tags.remove(tag)
            self.active_component_tag = next(iter(self.selected_component_tags), None)
        else:
            self.selected_component_tags.add(tag)
            self.active_component_tag = tag
            self.components[tag].set_selected(True)
        self._sync_component_wire_list_selection()
        self._render_property_editor()
        self._update_status_bar()

    def _build_wire_networks(self):
        node_owners = {
            node_canvas_id: wire
            for wire in self.wires
            for node_canvas_id in wire.node_canvas_ids
        }
        neighbors = {wire.wire_id: set() for wire in self.wires}
        wires_by_id = {wire.wire_id: wire for wire in self.wires}
        for wire in self.wires:
            for endpoint in (
                wire.start_endpoint_canvas_id, wire.end_endpoint_canvas_id
            ):
                owner = node_owners.get(endpoint)
                if owner is not None and owner is not wire:
                    neighbors[wire.wire_id].add(owner.wire_id)
                    neighbors[owner.wire_id].add(wire.wire_id)
        networks = []
        remaining = set(wires_by_id)
        while remaining:
            pending = [remaining.pop()]
            network_ids = set(pending)
            while pending:
                wire_id = pending.pop()
                additions = neighbors[wire_id] - network_ids
                network_ids.update(additions)
                remaining.difference_update(additions)
                pending.extend(additions)
            networks.append([wires_by_id[wire_id] for wire_id in network_ids])
        return networks

    def _network_component_tags(self, network):
        return {
            component_tag
            for wire in network
            for endpoint in (
                wire.start_endpoint_canvas_id, wire.end_endpoint_canvas_id
            )
            if (component_tag := self._terminal_component_tag(endpoint)) is not None
        }

    def _connected_wires_for_selected_components(self):
        return [
            wire
            for network in self._build_wire_networks()
            if self._network_component_tags(network) & self.selected_component_tags
            for wire in network
        ]

    def _internal_wires_for_selected_components(self):
        return [
            wire
            for network in self._build_wire_networks()
            if self._network_component_tags(network)
            and self._network_component_tags(network) <= self.selected_component_tags
            for wire in network
        ]

    def _move_wire_node_positions(self, wires, dx, dy):
        node_radius = self._wire_node_display_radius()
        for wire in wires:
            wire.node_positions = [
                (x + dx, y + dy) for x, y in wire.node_positions
            ]
            for node_canvas_id, (x, y) in zip(
                wire.node_canvas_ids, wire.node_positions
            ):
                self.canvas.coords(
                    node_canvas_id,
                    x - node_radius, y - node_radius,
                    x + node_radius, y + node_radius,
                )

    def _rotate_selection(self, pivot_tag, quarter_turns):
        if pivot_tag not in self.components:
            return
        if pivot_tag not in self.selected_component_tags:
            self._select_component(pivot_tag)
        selected_positions = [
            self._component_position(self.components[tag])
            for tag in self.selected_component_tags
            if tag in self.components
        ]
        if not selected_positions:
            return
        pivot_x = sum(x for x, _y in selected_positions) / len(selected_positions)
        pivot_y = sum(y for _x, y in selected_positions) / len(selected_positions)
        turns = quarter_turns % 4
        for tag in list(self.selected_component_tags):
            component = self.components.get(tag)
            if component is None:
                continue
            x, y = self._component_position(component)
            for _ in range(turns):
                x, y = pivot_x - (y - pivot_y), pivot_y + (x - pivot_x)
            old_x, old_y = self._component_position(component)
            component.move(x - old_x, y - old_y)
            component.rotate(quarter_turns)
        for wire in self._internal_wires_for_selected_components():
            rotated_nodes = []
            for x, y in wire.node_positions:
                for _ in range(turns):
                    x, y = pivot_x - (y - pivot_y), pivot_y + (x - pivot_x)
                rotated_nodes.append((x, y))
            wire.node_positions = rotated_nodes
            node_radius = self._wire_node_display_radius()
            for node_canvas_id, (x, y) in zip(
                wire.node_canvas_ids, wire.node_positions
            ):
                self.canvas.coords(
                    node_canvas_id,
                    x - node_radius, y - node_radius,
                    x + node_radius, y + node_radius,
                )
        self._update_all_wire_geometry()

    def _deselect_all(self) -> None:
        self._select_component(None)

    def _select_all_shortcut(self, event) -> str | None:
        if self._shortcut_uses_text_editor(event):
            return None
        self._clear_wire_selection()
        self._clear_component_selection()
        for tag, component in self.components.items():
            self.selected_component_tags.add(tag)
            component.set_selected(True)
        self.active_component_tag = next(reversed(self.components), None)
        self._sync_component_wire_list_selection()
        self._render_property_editor()
        self._update_status_bar()
        return "break"

    def _escape_shortcut(self, _event=None) -> str:
        if self.draft_wire_start_canvas_id is not None:
            self._cancel_wire()
        else:
            self._deselect_all()
        return "break"
