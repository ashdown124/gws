from __future__ import annotations

from .editor_models import WIRE_NODE_RADIUS, WireConnection


class WiringControllerMixin:
    """Wire creation, geometry, selection, and cascading deletion."""

    def _start_wire(self, terminal, x, y):
        self._clear_wire_selection(); self.wire_start_endpoint = terminal
        self.wire_nodes = []; self.wire_cursor = (x, y)
        self.canvas.configure(cursor="crosshair")
        self.canvas.itemconfigure(self.wire_mode_indicator, state="normal")
        self.canvas.tag_raise("ui_overlay"); self._redraw_wire_preview()
        self._update_status_bar()

    def _wire_points(self, start_endpoint, nodes, end):
        return [value for point in [self._endpoint_center(start_endpoint), *nodes, end] for value in point]

    def _redraw_wire_preview(self):
        for item in self.wire_preview_items: self.canvas.delete(item)
        self.wire_preview_items.clear()
        if self.wire_start_endpoint is None or self.wire_cursor is None: return
        self.wire_preview_items.append(self.canvas.create_line(
            *self._wire_points(self.wire_start_endpoint, self.wire_nodes, self.wire_cursor),
            fill="#2563eb", width=3, joinstyle="round", tags=("wire", "wire_preview")))
        for x, y in self.wire_nodes:
            self.wire_preview_items.append(self.canvas.create_oval(
                x-WIRE_NODE_RADIUS, y-WIRE_NODE_RADIUS,
                x+WIRE_NODE_RADIUS, y+WIRE_NODE_RADIUS,
                fill="#2563eb", outline="#ffffff", width=1,
                tags=("wire", "wire_preview", "wire_node")))
        self._raise_wires_above_components()

    def _finish_wire(self, end_endpoint):
        if self.wire_start_endpoint is None: return
        before = self._diagram_data(); start = self.wire_start_endpoint
        points = self._wire_points(start, self.wire_nodes, self._endpoint_center(end_endpoint))
        highlight = self.canvas.create_line(*points, fill="#f59e0b", width=9,
            joinstyle="round", state="hidden", tags=("wire", "wire_highlight"))
        line = self.canvas.create_line(*points, fill="#2563eb", width=3,
            joinstyle="round", tags=("wire",))
        nodes = [self.canvas.create_oval(
            x-WIRE_NODE_RADIUS, y-WIRE_NODE_RADIUS,
            x+WIRE_NODE_RADIUS, y+WIRE_NODE_RADIUS, fill="#2563eb",
            outline="#ffffff", width=1, tags=("wire", "wire_node")) for x,y in self.wire_nodes]
        self.wires.append(WireConnection(self.next_wire_id, highlight, line, start,
            end_endpoint, list(self.wire_nodes), nodes))
        self.next_wire_id += 1; self._cancel_wire(); self._raise_wires_above_components()
        self._refresh_element_list(); self._commit_history("wire_add", before)

    def _cancel_wire(self):
        for item in self.wire_preview_items: self.canvas.delete(item)
        self.wire_preview_items.clear(); self.wire_start_endpoint = None
        self.wire_nodes = []; self.wire_cursor = None; self.canvas.configure(cursor="arrow")
        self.canvas.itemconfigure(self.wire_mode_indicator, state="hidden")
        self._update_status_bar()

    def _raise_wires_above_components(self):
        self.canvas.tag_lower("grid"); self.canvas.tag_raise("wire"); self.canvas.tag_raise("ui_overlay")

    def _update_connections(self):
        for wire in self.wires: self._update_wire_geometry(wire)

    def _update_wire_geometry(self, wire):
        points = self._wire_points(wire.start_endpoint, wire.nodes, self._endpoint_center(wire.end_endpoint))
        self.canvas.coords(wire.highlight_id, *points); self.canvas.coords(wire.line_id, *points)

    def _delete_wire(self, wire):
        self.canvas.delete(wire.highlight_id); self.canvas.delete(wire.line_id)
        for node in wire.node_items: self.canvas.delete(node)

    def _remove_wire_cascade(self, wire):
        if wire not in self.wires: return
        self.wires.remove(wire)
        if self.selected_wire is wire:
            self.selected_wire = None
            self.selected_wire_node = None
        if self.wire_start_endpoint in wire.node_items: self._cancel_wire()
        for child in [candidate for candidate in self.wires
                      if candidate.start_endpoint in wire.node_items or candidate.end_endpoint in wire.node_items]:
            self._remove_wire_cascade(child)
        self._delete_wire(wire)

    def _select_wire(self, wire):
        self._clear_wire_selection()
        self._clear_component_selection()
        self.selected_tag = None; self.selected_wire = wire
        self.canvas.itemconfigure(wire.highlight_id, state="normal")
        self._sync_element_list_selection(); self._render_property_editor(); self._raise_wires_above_components()
        self._update_status_bar()

    def _select_wire_node(self, wire, node_item):
        self._select_wire(wire)
        self.canvas.itemconfigure(wire.highlight_id, state="hidden")
        self.selected_wire_node = (wire, node_item)
        self.canvas.itemconfigure(node_item, outline="#f59e0b", width=3)

    def _clear_wire_node_selection(self):
        if self.selected_wire_node is not None:
            _wire, node_item = self.selected_wire_node
            if self.canvas.type(node_item):
                self.canvas.itemconfigure(node_item, outline="#ffffff", width=1)
        self.selected_wire_node = None

    def _clear_wire_selection(self):
        self._clear_wire_node_selection()
        if self.selected_wire is not None:
            self.canvas.itemconfigure(self.selected_wire.highlight_id, state="hidden")
        self.selected_wire = None

    def _delete_selected_wire_node(self) -> bool:
        if self.selected_wire_node is None:
            return False
        wire, node_item = self.selected_wire_node
        if wire not in self.wires or node_item not in wire.node_items:
            self.selected_wire_node = None
            return False
        history_before = self._diagram_data()
        node_index = wire.node_items.index(node_item)
        for branch in list(self.wires):
            if branch is not wire and node_item in (
                branch.start_endpoint, branch.end_endpoint
            ):
                self._remove_wire_cascade(branch)
        self.canvas.delete(node_item)
        wire.node_items.pop(node_index)
        wire.nodes.pop(node_index)
        self.selected_wire_node = None
        self.selected_wire = wire
        self._update_wire_geometry(wire)
        self.canvas.itemconfigure(wire.highlight_id, state="normal")
        self._refresh_element_list()
        self._render_property_editor()
        self._commit_history("wire_node_delete", history_before)
        return True

    def _delete_connections_for_component(self, component_tag):
        for wire in list(self.wires):
            if component_tag in (self._terminal_component_tag(wire.start_endpoint),
                                 self._terminal_component_tag(wire.end_endpoint)):
                self._remove_wire_cascade(wire)

    def _clear_component_selection(self):
        for selected_tag in list(self.selected_tags):
            if selected_tag in self.components:
                self.components[selected_tag].set_selected(False)
        self.selected_tags.clear()

    def _select(self, tag, additive=False):
        self._clear_wire_selection()
        if not additive:
            self._clear_component_selection()
        if tag in self.components:
            self.selected_tags.add(tag)
            self.selected_tag = tag
            self.components[tag].set_selected(True)
        elif not additive:
            self.selected_tag = None
        self._sync_element_list_selection(); self._render_property_editor()
        self._update_status_bar()

    def _toggle_component_selection(self, tag):
        self._clear_wire_selection()
        if tag not in self.components:
            return
        if tag in self.selected_tags:
            self.components[tag].set_selected(False)
            self.selected_tags.remove(tag)
            self.selected_tag = next(iter(self.selected_tags), None)
        else:
            self.selected_tags.add(tag)
            self.selected_tag = tag
            self.components[tag].set_selected(True)
        self._sync_element_list_selection(); self._render_property_editor()
        self._update_status_bar()

    def _wire_networks(self):
        node_owners = {
            node_item: wire
            for wire in self.wires
            for node_item in wire.node_items
        }
        neighbors = {wire.wire_id: set() for wire in self.wires}
        wires_by_id = {wire.wire_id: wire for wire in self.wires}
        for wire in self.wires:
            for endpoint in (wire.start_endpoint, wire.end_endpoint):
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
            for endpoint in (wire.start_endpoint, wire.end_endpoint)
            if (component_tag := self._terminal_component_tag(endpoint)) is not None
        }

    def _connected_wires_for_selection(self):
        return [
            wire
            for network in self._wire_networks()
            if self._network_component_tags(network) & self.selected_tags
            for wire in network
        ]

    def _internal_wires_for_selection(self):
        return [
            wire
            for network in self._wire_networks()
            if self._network_component_tags(network)
            and self._network_component_tags(network) <= self.selected_tags
            for wire in network
        ]

    def _move_wire_nodes(self, wires, dx, dy):
        for wire in wires:
            wire.nodes = [(x + dx, y + dy) for x, y in wire.nodes]
            for node_item, (x, y) in zip(wire.node_items, wire.nodes):
                self.canvas.coords(
                    node_item,
                    x - WIRE_NODE_RADIUS, y - WIRE_NODE_RADIUS,
                    x + WIRE_NODE_RADIUS, y + WIRE_NODE_RADIUS,
                )

    def _rotate_selection(self, pivot_tag, quarter_turns):
        if pivot_tag not in self.components:
            return
        if pivot_tag not in self.selected_tags:
            self._select(pivot_tag)
        selected_positions = [
            self._component_position(self.components[tag])
            for tag in self.selected_tags
            if tag in self.components
        ]
        if not selected_positions:
            return
        pivot_x = sum(x for x, _y in selected_positions) / len(selected_positions)
        pivot_y = sum(y for _x, y in selected_positions) / len(selected_positions)
        turns = quarter_turns % 4
        for tag in list(self.selected_tags):
            component = self.components.get(tag)
            if component is None:
                continue
            x, y = self._component_position(component)
            for _ in range(turns):
                x, y = pivot_x - (y - pivot_y), pivot_y + (x - pivot_x)
            old_x, old_y = self._component_position(component)
            component.move(x - old_x, y - old_y)
            component.rotate(quarter_turns)
        for wire in self._internal_wires_for_selection():
            rotated_nodes = []
            for x, y in wire.nodes:
                for _ in range(turns):
                    x, y = pivot_x - (y - pivot_y), pivot_y + (x - pivot_x)
                rotated_nodes.append((x, y))
            wire.nodes = rotated_nodes
            for node_item, (x, y) in zip(wire.node_items, wire.nodes):
                self.canvas.coords(
                    node_item,
                    x - WIRE_NODE_RADIUS, y - WIRE_NODE_RADIUS,
                    x + WIRE_NODE_RADIUS, y + WIRE_NODE_RADIUS,
                )
        self._update_connections()

    def _deselect_all(self) -> None:
        self._select(None)

    def _select_all_shortcut(self, event) -> str | None:
        focused = event.widget.focus_get() if event.widget is not None else None
        if focused is not None and focused.winfo_class() in (
            "Entry", "TEntry", "TCombobox",
        ):
            return None
        self._clear_wire_selection()
        self._clear_component_selection()
        for tag, component in self.components.items():
            self.selected_tags.add(tag)
            component.set_selected(True)
        self.selected_tag = next(reversed(self.components), None)
        self._sync_element_list_selection()
        self._render_property_editor()
        self._update_status_bar()
        return "break"

    def _escape_shortcut(self, _event=None) -> str:
        if self.wire_start_endpoint is not None:
            self._cancel_wire()
        else:
            self._deselect_all()
        return "break"
