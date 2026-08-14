from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .components import COMPONENT_PROPERTY_SCHEMAS, CanvasComponent
from .editor_models import WIRE_COLORS


class PropertiesPanelMixin:
    """Component/wire property presentation, editing, and scrolling."""

    def _localized_option(self, value: str) -> str:
        if value.startswith("custom:"):
            definition = self.custom_switches.get(value.removeprefix("custom:"))
            return f"[custom] {definition.name}" if definition else value
        key = f"option_{value}"
        translated = self.localization.text(key)
        return value if translated == key else translated

    def _component_detail(self, component: CanvasComponent) -> str:
        schema = self._visible_component_schema(component)
        if not schema:
            return "-"
        if component.kind == "potentiometer":
            resistance = component.properties["resistance"]
            unit = component.properties["resistance_unit"]
            taper = self._localized_option(component.properties["taper"])
            return f"{resistance} {unit}, {taper}".strip()
        if component.kind == "pickup":
            pickup_type = self._localized_option(component.properties["pickup_type"])
            return (
                f"{pickup_type}, {component.properties['resistance']} "
                f"{component.properties['resistance_unit']}, "
                f"{component.properties['inductance']} "
                f"{component.properties['inductance_unit']}, "
                f"{component.properties['output_sensitivity']}%"
            )
        field = schema[0]
        value = component.properties[field["key"]]
        if field["type"] == "choice":
            detail = self._localized_option(value)
            return f"{detail}, P{component.switch_position}" if component.kind == "switch" else detail
        unit_key = f"{field['key']}_unit"
        return f"{value} {component.properties.get(unit_key, '')}".strip()

    def _update_properties_scrollregion(self, _event: tk.Event | None = None) -> None:
        self.properties_canvas.configure(scrollregion=self.properties_canvas.bbox("all"))

    def _resize_properties_content(self, event: tk.Event) -> None:
        self.properties_canvas.itemconfigure(self.properties_window, width=max(1, event.width - 10))

    def _scroll_properties(self, event: tk.Event, units: int | None = None) -> str:
        self.properties_canvas.yview_scroll(units if units is not None else (-1 if event.delta > 0 else 1), "units")
        return "break"

    def _bind_property_scrolling(self, widget: tk.Widget) -> None:
        widget.bind("<MouseWheel>", self._scroll_properties, add="+")
        widget.bind("<Button-4>", lambda event: self._scroll_properties(event, -1), add="+")
        widget.bind("<Button-5>", lambda event: self._scroll_properties(event, 1), add="+")
        for child in widget.winfo_children():
            self._bind_property_scrolling(child)

    def _finish_property_editor_render(self) -> None:
        self._bind_property_scrolling(self.properties_frame)
        self.properties_canvas.yview_moveto(0.0)
        self.root.after_idle(self._update_properties_scrollregion)

    def _render_property_editor(self) -> None:
        for child in self.properties_frame.winfo_children():
            child.destroy()
        self.property_widgets.clear()
        if self.selected_wire is not None:
            ttk.Label(self.properties_frame, text=self.localization.text("property_wire_color"),
                      style="Hint.TLabel").pack(anchor="w", pady=(6, 3))
            keys = list(WIRE_COLORS)
            editor = ttk.Combobox(
                self.properties_frame,
                values=[self.localization.text(f"color_{key}") for key in keys],
                state="readonly", width=15,
            )
            editor.current(keys.index(self.selected_wire.color))
            editor.pack(fill="x")
            self.property_widgets["wire_color"] = (tk.StringVar(value=self.selected_wire.color), editor)
            editor.bind("<<ComboboxSelected>>",
                        lambda _event: self.root.after_idle(self._apply_component_properties))
            self._finish_property_editor_render()
            return
        if len(self.selected_tags) > 1:
            ttk.Label(
                self.properties_frame,
                text=self.localization.text("multiple_selection"),
                style="Hint.TLabel",
            ).pack(anchor="w", pady=6)
            self._finish_property_editor_render()
            return
        if self.selected_tag not in self.components:
            ttk.Label(self.properties_frame, text=self.localization.text("no_selection"),
                      style="Hint.TLabel").pack(anchor="w", pady=6)
            self._finish_property_editor_render()
            return
        component = self.components[self.selected_tag]
        schema = self._visible_component_schema(component)
        if not schema:
            ttk.Label(self.properties_frame, text=self.localization.text("no_properties"),
                      style="Hint.TLabel").pack(anchor="w", pady=6)
            self._finish_property_editor_render()
            return
        for field in schema:
            ttk.Label(self.properties_frame, text=self.localization.text(field["label"]),
                      style="Hint.TLabel").pack(anchor="w", pady=(6, 3))
            row = ttk.Frame(self.properties_frame, style="Sidebar.TFrame")
            row.pack(fill="x")
            value_var = tk.StringVar(value=component.properties[field["key"]])
            if field["type"] == "choice":
                editor = ttk.Combobox(
                    row, values=[self._localized_option(value) for value in field["choices"]],
                    state="readonly", width=20,
                )
                editor.current(field["choices"].index(value_var.get()))
                editor.pack(fill="x", expand=True)
                editor.bind("<<ComboboxSelected>>",
                            lambda _event: self.root.after_idle(self._apply_component_properties))
            else:
                editor = ttk.Entry(row, textvariable=value_var, width=12)
                editor.pack(side="left", fill="x", expand=True)
                editor.bind("<Return>", lambda _event: self._apply_component_properties())
            self.property_widgets[field["key"]] = (value_var, editor)
            if "units" in field:
                unit_key = f"{field['key']}_unit"
                unit_var = tk.StringVar(value=component.properties[unit_key])
                unit_editor = ttk.Combobox(
                    row, textvariable=unit_var, values=field["units"], state="readonly", width=5
                )
                unit_editor.pack(side="left", padx=(5, 0))
                self.property_widgets[unit_key] = (unit_var, unit_editor)
                unit_editor.bind("<<ComboboxSelected>>",
                                 lambda _event: self.root.after_idle(self._apply_component_properties))
        self._finish_property_editor_render()

    def _apply_component_properties(self) -> None:
        history_before = self._diagram_data()
        if self.selected_wire is not None:
            selected_index = self.property_widgets["wire_color"][1].current()
            if selected_index >= 0:
                self.selected_wire.color = list(WIRE_COLORS)[selected_index]
                color = WIRE_COLORS[self.selected_wire.color]
                self.canvas.itemconfigure(self.selected_wire.line_id, fill=color)
                for node in self.selected_wire.node_items:
                    self.canvas.itemconfigure(node, fill=color)
                self._refresh_element_list()
                self._render_property_editor()
                self._commit_history("option_change", history_before)
            return
        if self.selected_tag not in self.components:
            return
        component = self.components[self.selected_tag]
        previous_pickup_type = component.properties.get("pickup_type")
        previous_switch_type = component.properties.get("switch_type")
        for field in self._visible_component_schema(component):
            value_var, editor = self.property_widgets[field["key"]]
            if field["type"] == "choice":
                if editor.current() >= 0:
                    component.properties[field["key"]] = field["choices"][editor.current()]
            else:
                value = value_var.get().strip()
                try:
                    if field["type"] == "number" and float(value) <= 0:
                        continue
                except ValueError:
                    continue
                component.properties[field["key"]] = value
            if "units" in field:
                unit_key = f"{field['key']}_unit"
                component.properties[unit_key] = self.property_widgets[unit_key][0].get()
        if component.kind == "pickup" and previous_pickup_type != component.properties.get("pickup_type"):
            self._delete_connections_for_component(component.tag)
        if component.kind == "switch" and previous_switch_type != component.properties.get("switch_type"):
            self._delete_connections_for_component(component.tag)
        component.update_visual()
        component.set_detail(self._component_detail(component))
        self._refresh_element_list()
        self._render_property_editor()
        self._commit_history("option_change", history_before)

    @staticmethod
    def _visible_component_schema(component: CanvasComponent) -> list[dict[str, object]]:
        return [
            field for field in COMPONENT_PROPERTY_SCHEMAS.get(component.kind, [])
            if not field.get("hidden", False)
        ]
