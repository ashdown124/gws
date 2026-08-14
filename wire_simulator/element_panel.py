from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .editor_models import WireConnection


PICKUP_TRACE_COLORS = ("#f97316", "#a855f7", "#eab308", "#ef4444", "#14b8a6")


class ElementPanelMixin:
    """Component/wire lists, ordering controls, and pickup trace selectors."""

    def _refresh_element_list(self) -> None:
        self.element_list.delete(0, tk.END)
        self.wire_list.delete(0, tk.END)
        self.element_list_tags = list(self.components)
        self.wire_list_references = [self._wire_reference(wire) for wire in self.wires]
        if not self.element_list_tags:
            self.element_list.insert(tk.END, self.localization.text("elements_empty"))
            self.element_list.itemconfigure(0, foreground="#7f8b99")
            self._update_order_button_states()
        else:
            for tag, component in self.components.items():
                label = (
                    component.custom_name
                    or self.localization.text(f"component_{component.kind}")
                )
                self.element_list.insert(
                    tk.END,
                    f"#{component.component_id}  {label}  [{self._component_detail(component)}]",
                )
        if not self.wires:
            self.wire_list.insert(tk.END, self.localization.text("wires_empty"))
            self.wire_list.itemconfigure(0, foreground="#7f8b99")
        for wire in self.wires:
            color = self.localization.text(f"color_{wire.color}")
            detail = self.localization.text("wire_detail").format(
                color=color, count=len(wire.nodes)
            )
            self.wire_list.insert(
                tk.END, f"W#{wire.wire_id}  {self.localization.text('wire_label')}  [{detail}]"
            )
        self._sync_element_list_selection()
        self._refresh_pickup_trace_controls()
        self._update_add_component_button_state()
        self._raise_wires_above_components()
        self._refresh_document_state()

    def _refresh_pickup_trace_controls(self) -> None:
        source_keys = self._pickup_source_keys()
        previous = {key: variable.get() for key, variable in self.pickup_trace_vars.items()}
        for child in self.pickup_traces_frame.winfo_children():
            child.destroy()
        self.pickup_trace_vars = {}
        if not source_keys:
            ttk.Label(
                self.pickup_traces_frame,
                text=self.localization.text("pickup_traces_empty"),
                style="Hint.TLabel",
            ).pack(anchor="w")
            return
        for source_key in source_keys:
            variable = tk.BooleanVar(value=previous.get(source_key, False))
            self.pickup_trace_vars[source_key] = variable
            component_id, separator, coil = source_key.partition(":")
            label_key = "pickup_trace_coil_label" if separator else "pickup_trace_label"
            component = next(
                (
                    item for item in self.components.values()
                    if str(item.component_id) == component_id
                ),
                None,
            )
            display_name = (
                component.custom_name
                if component is not None and component.custom_name
                else self.localization.text("component_pickup")
            )
            color = self._pickup_trace_color(source_key)
            tk.Checkbutton(
                self.pickup_traces_frame,
                text=self.localization.text(label_key).format(
                    name=display_name, id=component_id, coil=coil
                ),
                variable=variable,
                command=self._redraw_signal_graphs,
                bg="#202936", fg=color,
                activebackground="#202936", activeforeground=color,
                selectcolor="#111821", font=("Malgun Gothic", 9), anchor="w",
            ).pack(anchor="w")

    def _pickup_source_keys(self) -> list[str]:
        source_keys: list[str] = []
        for component in self.components.values():
            if component.kind != "pickup":
                continue
            if component.properties["pickup_type"] == "humbucker":
                source_keys.extend((f"{component.component_id}:N", f"{component.component_id}:S"))
            else:
                source_keys.append(str(component.component_id))
        return source_keys

    def _pickup_trace_color(self, source_key: str) -> str:
        source_keys = self._pickup_source_keys()
        index = source_keys.index(source_key) if source_key in source_keys else 0
        return PICKUP_TRACE_COLORS[index % len(PICKUP_TRACE_COLORS)]

    def _update_order_button_states(self) -> None:
        ordered_tags = list(self.components)
        selected_tags = self.selected_tags & set(ordered_tags)
        if not selected_tags:
            self.move_up_button.configure(state="disabled")
            self.move_down_button.configure(state="disabled")
            return
        can_move_up = any(
            index > 0 and ordered_tags[index - 1] not in selected_tags
            for index, tag in enumerate(ordered_tags) if tag in selected_tags
        )
        can_move_down = any(
            index < len(ordered_tags) - 1
            and ordered_tags[index + 1] not in selected_tags
            for index, tag in enumerate(ordered_tags) if tag in selected_tags
        )
        self.move_up_button.configure(state="normal" if can_move_up else "disabled")
        self.move_down_button.configure(state="normal" if can_move_down else "disabled")

    def _move_selected_element(self, direction: int) -> None:
        selected_tags = self.selected_tags & set(self.components)
        if not selected_tags:
            return
        ordered_tags = list(self.components)
        selected_in_order = [tag for tag in ordered_tags if tag in selected_tags]
        if direction < 0:
            for tag in selected_in_order:
                index = ordered_tags.index(tag)
                if index > 0 and ordered_tags[index - 1] not in selected_tags:
                    ordered_tags[index - 1], ordered_tags[index] = (
                        ordered_tags[index], ordered_tags[index - 1]
                    )
        else:
            for tag in reversed(selected_in_order):
                index = ordered_tags.index(tag)
                if (
                    index < len(ordered_tags) - 1
                    and ordered_tags[index + 1] not in selected_tags
                ):
                    ordered_tags[index], ordered_tags[index + 1] = (
                        ordered_tags[index + 1], ordered_tags[index]
                    )
        self.components = {tag: self.components[tag] for tag in ordered_tags}
        self._apply_canvas_stack_order()
        self._refresh_element_list()

    def _apply_canvas_stack_order(self) -> None:
        for tag in reversed(self.components):
            self.canvas.tag_raise(tag)
        self._raise_wires_above_components()

    def _select_from_element_list(self, _event: tk.Event) -> None:
        selection = [
            index for index in self.element_list.curselection()
            if index < len(self.element_list_tags)
        ]
        if not selection or not self.element_list_tags:
            return
        self._clear_wire_selection()
        self._clear_component_selection()
        for index in selection:
            tag = self.element_list_tags[index]
            self.selected_tags.add(tag)
            self.components[tag].set_selected(True)
        self.selected_tag = self.element_list_tags[selection[-1]]
        self._sync_element_list_selection()
        self._render_property_editor()
        self._update_status_bar()

    def _select_from_wire_list(self, _event: tk.Event) -> None:
        selection = self.wire_list.curselection()
        if selection and self.wire_list_references:
            wire = self._wire_from_reference(self.wire_list_references[selection[0]])
            if wire is not None:
                self._select_wire(wire)

    @staticmethod
    def _wire_reference(wire: WireConnection) -> str:
        return f"wire_{wire.wire_id}"

    def _wire_from_reference(self, reference: str) -> WireConnection | None:
        return next((wire for wire in self.wires if self._wire_reference(wire) == reference), None)

    def _sync_element_list_selection(self) -> None:
        self.element_list.selection_clear(0, tk.END)
        self.wire_list.selection_clear(0, tk.END)
        if self.selected_wire is not None:
            reference = self._wire_reference(self.selected_wire)
            if reference in self.wire_list_references:
                index = self.wire_list_references.index(reference)
                self.wire_list.selection_set(index)
                self.wire_list.activate(index)
                self.wire_list.see(index)
        else:
            selected_indices = [
                self.element_list_tags.index(tag)
                for tag in self.selected_tags
                if tag in self.element_list_tags
            ]
            for index in selected_indices:
                self.element_list.selection_set(index)
            if self.selected_tag in self.element_list_tags:
                index = self.element_list_tags.index(self.selected_tag)
                self.element_list.activate(index)
                self.element_list.see(index)
        self._update_order_button_states()
