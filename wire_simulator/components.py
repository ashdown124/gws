from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tkinter as tk

from .component_symbols import ComponentSymbolRenderer
from .custom_switches import CustomSwitchDefinition


@dataclass(frozen=True)
class ComponentStyle:
    color: str
    width: int = 120
    height: int = 64


COMPONENT_STYLES = {
    "pickup": ComponentStyle("#d97757", 150, 128),
    "potentiometer": ComponentStyle("#4f9d8f", 120, 120),
    "resistor": ComponentStyle("#d7a93f", 65, 36),
    "capacitor": ComponentStyle("#5987c9", 65, 36),
    "switch": ComponentStyle("#8b6fc2", 190, 220),
    "jack": ComponentStyle("#607d8b", 120, 118),
    "ground": ComponentStyle("#374151", 80, 90),
}

COMPONENT_PROPERTY_SCHEMAS = {
    "pickup": [
        {"key": "pickup_type", "label": "property_pickup_type", "type": "choice",
         "choices": ["single", "single_rwrp", "humbucker"], "default": "single"},
        {"key": "resistance", "label": "property_pickup_resistance", "type": "number",
         "default": "7", "units": ["Ω", "kΩ", "MΩ"], "default_unit": "kΩ"},
        {"key": "inductance", "label": "property_inductance", "type": "number",
         "default": "4", "units": ["mH", "H"], "default_unit": "H"},
        {"key": "output_sensitivity", "label": "property_output_sensitivity", "type": "number",
         "default": "100"},
    ],
    "potentiometer": [
        {"key": "resistance", "label": "property_resistance", "type": "number",
         "default": "500", "units": ["kΩ", "MΩ"], "default_unit": "kΩ"},
        {"key": "taper", "label": "property_taper", "type": "choice",
         "choices": ["audio_taper", "linear_taper", "reverse_audio_taper"],
         "default": "audio_taper"},
    ],
    "resistor": [{"key": "resistance", "label": "property_resistance", "type": "number",
                  "default": "10", "units": ["Ω", "kΩ", "MΩ"], "default_unit": "kΩ"}],
    "capacitor": [{"key": "capacitance", "label": "property_capacitance", "type": "number",
                   "default": "47", "units": ["pF", "nF", "µF"], "default_unit": "nF"}],
    "switch": [{"key": "switch_type", "label": "property_switch_type", "type": "choice",
                "choices": ["blade_3way", "blade_5way", "toggle_3way"],
                "default": "blade_3way"}],
    # Keep the mono value in diagram data for format compatibility, but it is
    # not user-configurable while only one jack implementation exists.
    "jack": [{"key": "jack_type", "label": "property_jack_type", "type": "choice",
              "choices": ["mono"], "default": "mono", "hidden": True}],
}

BUILTIN_SWITCH_TYPES = ("blade_3way", "blade_5way", "toggle_3way")
CUSTOM_SWITCH_DEFINITIONS: dict[str, CustomSwitchDefinition] = {}
CONTROL_ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"


def _canvas_control_icons(canvas: tk.Canvas) -> dict[str, tk.PhotoImage]:
    cached = getattr(canvas, "_gws_control_icons", None)
    if cached is not None:
        return cached
    icons: dict[str, tk.PhotoImage] = {}
    for name in ("rotate_ccw", "rotate_cw", "rename"):
        try:
            source = tk.PhotoImage(master=canvas, file=str(CONTROL_ICON_DIR / f"{name}.png"))
            scale = max(1, math.ceil(max(source.width(), source.height()) / 16))
            icons[name] = source.subsample(scale, scale) if scale > 1 else source
        except tk.TclError:
            continue
    setattr(canvas, "_gws_control_icons", icons)
    return icons


def configure_custom_switches(
    definitions: dict[str, CustomSwitchDefinition],
) -> None:
    global CUSTOM_SWITCH_DEFINITIONS
    CUSTOM_SWITCH_DEFINITIONS = dict(definitions)
    switch_schema = COMPONENT_PROPERTY_SCHEMAS["switch"][0]
    switch_schema["choices"] = [
        *BUILTIN_SWITCH_TYPES,
        *(f"custom:{switch_id}" for switch_id in definitions),
    ]

BLADE_SWITCH_ACTIVE_TERMINALS = {
    "blade_3way": {
        1: {"A0", "A1", "B0", "B1"},
        2: {"A0", "A2", "B0", "B2"},
        3: {"A0", "A3", "B0", "B3"},
    },
    "blade_5way": {
        1: {"A0", "A1", "B0", "B1"},
        2: {"A0", "A1", "A2", "B0", "B1", "B2"},
        3: {"A0", "A2", "B0", "B2"},
        4: {"A0", "A2", "A3", "B0", "B2", "B3"},
        5: {"A0", "A3", "B0", "B3"},
    },
}

TOGGLE_SWITCH_ACTIVE_TERMINALS = {
    1: {"A", "A_prime"},
    2: {"A", "A_prime", "B", "B_prime"},
    3: {"B", "B_prime"},
}


class CanvasComponent(ComponentSymbolRenderer):
    """A movable component drawn as one tagged Canvas item group."""

    def __init__(self, canvas: tk.Canvas, component_id: int, kind: str,
                 label: str, x: float, y: float) -> None:
        self.canvas = canvas
        self.control_icons = _canvas_control_icons(canvas)
        self.component_id = component_id
        self.kind = kind
        self.style = COMPONENT_STYLES[kind]
        self.tag = f"component_{component_id}"
        self.label_tag = f"component_label_{component_id}"
        self.detail_tag = f"component_detail_{component_id}"
        self.selection_tag = f"component_selection_{component_id}"
        self.rename_control_tag = f"rename_controls_{component_id}"
        self.pickup_single_tag = f"pickup_single_{component_id}"
        self.pickup_humbucker_tag = f"pickup_humbucker_{component_id}"
        self.gauge_track_tag = f"pot_gauge_track_{component_id}"
        self.gauge_fill_tag = f"pot_gauge_fill_{component_id}"
        self.gauge_text_tag = f"pot_gauge_text_{component_id}"
        self.gauge_value = 50
        self.terminals: dict[str, int] = {}
        self.external_terminal_labels: dict[str, int] = {}
        self.switch_position = 1
        self.active_switch_terminals: set[str] = set()
        self.switch_track_tag = f"switch_track_{component_id}"
        self.blade_symbol_tag = f"blade_symbol_{component_id}"
        self.toggle_symbol_tag = f"toggle_symbol_{component_id}"
        self.toggle_lever_tag = f"toggle_lever_{component_id}"
        self.custom_symbol_tag = f"custom_switch_symbol_{component_id}"
        self.custom_connection_tag = f"custom_switch_connection_{component_id}"
        self.custom_switch_definition: CustomSwitchDefinition | None = None
        self.custom_switch_center: tuple[float, float] | None = None
        self.switch_position_text_tag = f"switch_position_text_{component_id}"
        self.hitbox_bounds: tuple[float, float, float, float] | None = None
        self.properties: dict[str, str] = {}
        for field in COMPONENT_PROPERTY_SCHEMAS.get(kind, []):
            self.properties[field["key"]] = field["default"]
            if "units" in field:
                self.properties[f"{field['key']}_unit"] = field["default_unit"]
        self.selected = False
        self.custom_name = ""
        self.rotation = 0
        self._draw(label, x, y)

    def _draw(self, label: str, x: float, y: float) -> None:
        half_w = self.style.width / 2
        half_h = self.style.height / 2
        x1, y1, x2, y2 = x - half_w, y - half_h, x + half_w, y + half_h
        is_external_label_symbol = self.kind in (
            "pickup", "potentiometer", "resistor", "capacitor", "jack", "ground", "switch"
        )
        if is_external_label_symbol:
            self.hitbox_bounds = (x1 - 7, y1 - 5, x2 + 7, y2 + 5)
            if self.kind == "pickup":
                hitbox_x1, hitbox_y1, hitbox_x2, hitbox_y2 = self.hitbox_bounds
                self.hitbox_bounds = (
                    hitbox_x1, hitbox_y1 + 18,
                    hitbox_x2, hitbox_y2 - 14,
                )
            elif self.kind == "potentiometer":
                hitbox_x1, hitbox_y1, hitbox_x2, hitbox_y2 = self.hitbox_bounds
                self.hitbox_bounds = (
                    hitbox_x1, hitbox_y1 + 15,
                    hitbox_x2, hitbox_y2,
                )
            elif self.kind in ("resistor", "capacitor"):
                hitbox_x1, hitbox_y1, hitbox_x2, hitbox_y2 = self.hitbox_bounds
                extra_x = (hitbox_x2 - hitbox_x1) * 0.31
                extra_y = (hitbox_y2 - hitbox_y1) * 0.31
                self.hitbox_bounds = (
                    hitbox_x1 - extra_x, hitbox_y1 - extra_y,
                    hitbox_x2 + extra_x, hitbox_y2 + extra_y,
                )
            self.canvas.create_rectangle(
                *self.hitbox_bounds, fill="", outline="",
                tags=("component", "component_hitbox", self.tag),
            )
        if self.kind == "pickup":
            self._draw_pickup_symbol(x1, x2, x, y)
        elif self.kind == "potentiometer":
            self._draw_potentiometer_symbol(x, y)
        elif self.kind == "jack":
            self._draw_jack_symbol(x, y)
        elif self.kind == "ground":
            self._draw_ground_symbol(x, y)
        elif self.kind == "switch":
            self._draw_blade_switch_symbol(x, y)
            self._draw_toggle_switch_symbol(x, y)
        elif self.kind == "resistor":
            self._draw_resistor_symbol(x1, x2, x, y)
        elif self.kind == "capacitor":
            self._draw_capacitor_symbol(x1, x2, x, y)
        else:
            self.canvas.create_rectangle(
                x1, y1, x2, y2, fill=self.style.color, outline="#202936", width=2,
                tags=("component", "component_body", self.tag),
            )
        self.canvas.create_text(
            x, y - (102 if self.kind == "switch" else 35 if self.kind == "pickup" else 58 if self.kind == "jack" else 42 if self.kind == "ground" else 48 if self.kind == "potentiometer" else 32 if is_external_label_symbol else 7),
            text=label,
            fill="#202936" if is_external_label_symbol else "white",
            font=("Malgun Gothic", 11, "bold"),
            tags=("component", self.label_tag, self.tag),
        )
        self.canvas.create_text(
            x, y + (102 if self.kind == "switch" else 58 if self.kind in ("pickup", "jack") else 40 if self.kind == "ground" else 68 if self.kind == "potentiometer" else 32 if is_external_label_symbol else 14),
            text=f"#{self.component_id}",
            fill="#3c4858" if is_external_label_symbol else "#edf2f7",
            font=("Arial", 9), tags=("component", self.detail_tag, self.tag),
        )
        if self.kind not in ("pickup", "potentiometer", "jack", "ground", "switch"):
            terminal_radius = 7 if self.kind in ("resistor", "capacitor") else 5
            for terminal_name, terminal_x in zip(("1", "2"), (x1, x2)):
                terminal = self.canvas.create_oval(
                    terminal_x - terminal_radius, y - terminal_radius,
                    terminal_x + terminal_radius, y + terminal_radius,
                    fill="#f8fafc", outline="#202936", width=2,
                    tags=("component", "terminal", self.tag),
                )
                self.terminals[terminal_name] = terminal
        selection_bounds = self.hitbox_bounds or (x1 - 7, y1 - 5, x2 + 7, y2 + 5)
        self.canvas.create_rectangle(
            *selection_bounds,
            outline="#ffbf00", width=3, dash=(6, 3), state="hidden",
            tags=("component", self.selection_tag, self.tag),
        )
        self._draw_rotation_controls()
        self._draw_rename_control()
        self.update_visual()
        self._position_external_text()

    def _draw_rotation_controls(self) -> None:
        """Draw compact rotation controls without making their glyphs rotate."""
        for direction in ("ccw", "cw"):
            button_tag = f"rotate_{direction}_{self.component_id}"
            self.canvas.create_rectangle(
                0, 0, 18, 18, fill="#ffffff", outline="#64748b", width=1,
                state="hidden",
                tags=("component", "ui_overlay", "rotation_control", f"rotation_controls_{self.component_id}", f"rotate_{direction}",
                      button_tag, self.tag),
            )
            icon = self.control_icons.get(f"rotate_{direction}")
            if icon is not None:
                self.canvas.create_image(
                    0, 0, image=icon, state="hidden",
                    tags=("component", "ui_overlay", "rotation_control",
                          f"rotation_controls_{self.component_id}", f"rotate_{direction}",
                          button_tag, self.tag),
                )
            else:
                self.canvas.create_line(
                    0, 0, 0, 0, 0, 0,
                    fill="#111827", width=2, joinstyle="round",
                    arrow=tk.LAST, arrowshape=(5, 6, 2),
                    state="hidden",
                    tags=("component", "ui_overlay", "rotation_control",
                          f"rotation_controls_{self.component_id}", f"rotate_{direction}",
                          button_tag, self.tag),
                )
        self._position_rotation_controls()

    def _position_rotation_controls(self) -> None:
        if self.hitbox_bounds is None:
            return
        x1, y1, _, _ = self.hitbox_bounds
        for index, direction in enumerate(("ccw", "cw")):
            left = x1 + 3 + index * 21
            top = y1 + 3
            items = self.canvas.find_withtag(f"rotate_{direction}_{self.component_id}")
            for item in items:
                if self.canvas.type(item) == "rectangle":
                    self.canvas.coords(item, left, top, left + 18, top + 18)
                elif self.canvas.type(item) == "line":
                    if direction == "ccw":
                        self.canvas.coords(
                            item,
                            left + 14, top + 14,
                            left + 14, top + 6,
                            left + 5, top + 6,
                        )
                    else:
                        self.canvas.coords(
                            item,
                            left + 4, top + 14,
                            left + 4, top + 6,
                            left + 13, top + 6,
                        )
                else:
                    self.canvas.coords(item, left + 9, top + 9)
        self._position_rename_control()

    def _draw_rename_control(self) -> None:
        common_tags = (
            "component", "ui_overlay", "rename_control",
            self.rename_control_tag, self.tag,
        )
        self.canvas.create_rectangle(
            0, 0, 18, 18, fill="#ffffff", outline="#64748b", width=1,
            state="hidden", tags=common_tags,
        )
        icon = self.control_icons.get("rename")
        if icon is not None:
            self.canvas.create_image(
                0, 0, image=icon, state="hidden", tags=common_tags,
            )
        else:
            self.canvas.create_line(
                0, 0, 0, 0, fill="#111827", width=3, capstyle="round",
                state="hidden", tags=common_tags,
            )
            self.canvas.create_line(
                0, 0, 0, 0, fill="#111827", width=1,
                state="hidden", tags=common_tags,
            )
        self._position_rename_control()

    def _position_rename_control(self) -> None:
        if self.hitbox_bounds is None:
            return
        _x1, y1, x2, _y2 = self.hitbox_bounds
        left, top = x2 - 21, y1 + 3
        for item in self.canvas.find_withtag(self.rename_control_tag):
            if self.canvas.type(item) == "rectangle":
                self.canvas.coords(item, left, top, left + 18, top + 18)
            elif self.canvas.type(item) == "image":
                self.canvas.coords(item, left + 9, top + 9)
            elif len(self.canvas.coords(item)) == 4:
                if self.canvas.itemcget(item, "width") == "3.0":
                    self.canvas.coords(item, left + 5, top + 13, left + 13, top + 5)
                else:
                    self.canvas.coords(item, left + 4, top + 14, left + 7, top + 13)

    def _position_external_text(self) -> None:
        """Keep the component name and detail horizontal outside the hitbox."""
        if self.hitbox_bounds is None:
            return
        x1, y1, x2, y2 = self.hitbox_bounds
        center_x = (x1 + x2) / 2
        self.canvas.coords(self.label_tag, center_x, y1 - 7)
        self.canvas.coords(self.detail_tag, center_x, y2 + 9)

    def _position_external_terminal_labels(self) -> None:
        """Place jack and built-in switch labels outside their terminal circles."""
        if self.hitbox_bounds is None:
            return
        x1, y1, x2, y2 = self.hitbox_bounds
        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
        label_gap = 12
        for terminal_name, label_item in self.external_terminal_labels.items():
            terminal_item = self.terminals.get(terminal_name)
            if terminal_item is None:
                continue
            terminal_bounds = self.canvas.coords(terminal_item)
            if len(terminal_bounds) != 4:
                continue
            terminal_x = (terminal_bounds[0] + terminal_bounds[2]) / 2
            terminal_y = (terminal_bounds[1] + terminal_bounds[3]) / 2
            offset_x = terminal_x - center_x
            offset_y = terminal_y - center_y
            if abs(offset_x) >= abs(offset_y):
                direction = 1 if offset_x >= 0 else -1
                self.canvas.coords(label_item, terminal_x + direction * label_gap, terminal_y)
                self.canvas.itemconfigure(label_item, anchor="w" if direction > 0 else "e")
            else:
                direction = 1 if offset_y >= 0 else -1
                self.canvas.coords(label_item, terminal_x, terminal_y + direction * label_gap)
                self.canvas.itemconfigure(label_item, anchor="n" if direction > 0 else "s")

    def _fit_hitbox_to_visible_geometry(self) -> None:
        """Expand the hitbox so visible geometry stays clear of its controls."""
        if self.hitbox_bounds is None:
            return
        self._position_external_terminal_labels()

        bounds: list[tuple[int, int, int, int]] = []
        for item in self.canvas.find_withtag(self.tag):
            tags = self.canvas.gettags(item)
            if (
                "component_hitbox" in tags
                or "ui_overlay" in tags
                or self.selection_tag in tags
                or self.label_tag in tags
                or self.detail_tag in tags
                or self.canvas.itemcget(item, "state") == "hidden"
            ):
                continue
            item_bounds = self.canvas.bbox(item)
            if item_bounds is not None:
                bounds.append(item_bounds)
        if not bounds:
            return

        content_x1 = min(bound[0] for bound in bounds)
        content_y1 = min(bound[1] for bound in bounds)
        content_x2 = max(bound[2] for bound in bounds)
        content_y2 = max(bound[3] for bound in bounds)
        x1, y1, x2, y2 = self.hitbox_bounds
        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2

        # The top row contains two rotation buttons and one rename button.
        # Keep the bounds centered so repeated rotations do not move the symbol.
        half_width = max(
            (x2 - x1) / 2,
            center_x - content_x1 + 5,
            content_x2 - center_x + 5,
            35,
        )
        half_height = max(
            (y2 - y1) / 2,
            center_y - content_y1 + 25,
            content_y2 - center_y + 5,
        )
        self.hitbox_bounds = (
            center_x - half_width, center_y - half_height,
            center_x + half_width, center_y + half_height,
        )

        for item in self.canvas.find_withtag(self.tag):
            if "component_hitbox" in self.canvas.gettags(item):
                self.canvas.coords(item, *self.hitbox_bounds)
                break
        self.canvas.coords(self.selection_tag, *self.hitbox_bounds)
        self._position_external_text()
        self._position_rotation_controls()
        self._position_rename_control()

    def _rotate_geometry(self, quarter_turns: int) -> None:
        if self.hitbox_bounds is None:
            return
        turns = quarter_turns % 4
        if turns == 0:
            return
        x1, y1, x2, y2 = self.hitbox_bounds
        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
        for _ in range(turns):
            for item in self.canvas.find_withtag(self.tag):
                tags = self.canvas.gettags(item)
                if (
                    "rotation_control" in tags
                    or "rename_control" in tags
                    or self.label_tag in tags
                    or self.detail_tag in tags
                ):
                    continue
                coords = self.canvas.coords(item)
                rotated: list[float] = []
                for point_x, point_y in zip(coords[::2], coords[1::2]):
                    rotated.extend((center_x - (point_y - center_y),
                                    center_y + (point_x - center_x)))
                if self.canvas.type(item) in ("rectangle", "oval", "arc") and len(rotated) == 4:
                    rotated = [min(rotated[0], rotated[2]), min(rotated[1], rotated[3]),
                               max(rotated[0], rotated[2]), max(rotated[1], rotated[3])]
                self.canvas.coords(item, *rotated)
            width, height = x2 - x1, y2 - y1
            x1, y1 = center_x - height / 2, center_y - width / 2
            x2, y2 = center_x + height / 2, center_y + width / 2
        self.hitbox_bounds = (x1, y1, x2, y2)
        self._position_external_text()
        self._position_rotation_controls()
        self._position_rename_control()

    def rotate(self, quarter_turns: int) -> None:
        self._rotate_geometry(quarter_turns)
        self.rotation = (self.rotation + quarter_turns * 90) % 360
        self._fit_hitbox_to_visible_geometry()

    def _begin_visual_update(self) -> int:
        rotation = self.rotation
        if rotation:
            self._rotate_geometry(-(rotation // 90))
            self.rotation = 0
        return rotation

    def _end_visual_update(self, rotation: int) -> None:
        if rotation:
            self._rotate_geometry(rotation // 90)
            self.rotation = rotation
        self._fit_hitbox_to_visible_geometry()









    def set_label(self, label: str) -> None:
        self.canvas.itemconfigure(self.label_tag, text=label)

    def set_custom_name(self, name: str, default_label: str) -> None:
        self.custom_name = name.strip()
        self.set_label(self.custom_name or default_label)

    def set_detail(self, detail: str) -> None:
        self.canvas.itemconfigure(self.detail_tag, text=f"#{self.component_id} · {detail}")

    def set_gauge_value(self, value: int) -> None:
        rotation = self._begin_visual_update()
        self.gauge_value = max(0, min(100, int(value)))
        track_items = self.canvas.find_withtag(self.gauge_track_tag)
        if not track_items:
            self._end_visual_update(rotation)
            return
        x1, y1, x2, y2 = self.canvas.coords(track_items[0])
        left, right = x1 + 5.6, x2 - 5.6
        target_x = left + (right - left) * self.gauge_value / 100
        center_x = (x1 + x2) / 2
        resistor_y = (y1 + y2) / 2
        self.canvas.coords(
            self.gauge_fill_tag,
            center_x, y2 + 31.2,
            center_x, y2 + 14.4,
            target_x, y2 + 14.4,
            target_x, resistor_y + 3.2,
        )
        self.canvas.itemconfigure(self.gauge_text_tag, text=str(self.gauge_value))
        self._end_visual_update(rotation)

    def update_visual(self) -> None:
        rotation = self._begin_visual_update()
        if self.kind == "switch":
            switch_type = self.properties["switch_type"]
            is_toggle = switch_type == "toggle_3way"
            is_custom = switch_type.startswith("custom:")
            self.canvas.itemconfigure(
                self.blade_symbol_tag,
                state="hidden" if is_toggle or is_custom else "normal",
            )
            self.canvas.itemconfigure(
                self.toggle_symbol_tag, state="normal" if is_toggle else "hidden"
            )
            if is_custom:
                switch_id = switch_type.removeprefix("custom:")
                self._show_custom_switch(CUSTOM_SWITCH_DEFINITIONS[switch_id])
            else:
                self._clear_custom_switch()
                self._set_switch_visual_bounds(160 if is_toggle else 190,
                                               180 if is_toggle else 220)
            self.set_switch_position(self.switch_position)
            self._end_visual_update(rotation)
            return
        if self.kind != "pickup":
            self._end_visual_update(rotation)
            return
        is_humbucker = self.properties["pickup_type"] == "humbucker"
        self.canvas.itemconfigure(
            self.pickup_single_tag, state="hidden" if is_humbucker else "normal"
        )
        self.canvas.itemconfigure(
            self.pickup_humbucker_tag, state="normal" if is_humbucker else "hidden"
        )
        self._end_visual_update(rotation)

    def set_switch_position(self, position: int) -> None:
        if self.kind != "switch":
            return
        rotation = self._begin_visual_update()
        switch_type = self.properties["switch_type"]
        if switch_type.startswith("custom:"):
            definition = CUSTOM_SWITCH_DEFINITIONS[switch_type.removeprefix("custom:")]
            max_position = len(definition.positions)
        else:
            max_position = 5 if switch_type == "blade_5way" else 3
        self.switch_position = max(1, min(max_position, int(position)))
        if switch_type.startswith("custom:"):
            position_definition = definition.positions[self.switch_position - 1]
            self.active_switch_terminals = {
                terminal for group in position_definition.connections for terminal in group
            }
            self._draw_custom_connections(position_definition.connections)
        elif switch_type == "toggle_3way":
            self.active_switch_terminals = set(
                TOGGLE_SWITCH_ACTIVE_TERMINALS[self.switch_position]
            )
        else:
            self.active_switch_terminals = set(
                BLADE_SWITCH_ACTIVE_TERMINALS[switch_type][self.switch_position]
            )
        for terminal_name in ("A0", "A1", "A2", "A3", "B0", "B1", "B2", "B3"):
            if terminal_name in self.active_switch_terminals:
                fill = "#16a34a" if terminal_name.startswith("A") else "#ea580c"
            else:
                fill = "#ffffff"
            self.canvas.itemconfigure(
                f"switch_terminal_{terminal_name}_{self.component_id}", fill=fill
            )
        for terminal_name in ("A", "A_prime", "B", "B_prime"):
            self.canvas.itemconfigure(
                f"toggle_terminal_{terminal_name}_{self.component_id}",
                fill="#f59e0b" if terminal_name in self.active_switch_terminals else "#ffffff",
            )
        self.canvas.itemconfigure(
            f"toggle_connection_A_{self.component_id}",
            state="normal" if {"A", "A_prime"} <= self.active_switch_terminals else "hidden",
        )
        self.canvas.itemconfigure(
            f"toggle_connection_B_{self.component_id}",
            state="normal" if {"B", "B_prime"} <= self.active_switch_terminals else "hidden",
        )
        if switch_type == "toggle_3way":
            lever_end_x = {1: 18, 2: 0, 3: -18}[self.switch_position]
            lever_items = self.canvas.find_withtag(self.toggle_lever_tag)
            if lever_items:
                x1, y1, _, _ = self.canvas.coords(lever_items[0])
                self.canvas.coords(lever_items[0], x1, y1, x1 + lever_end_x, y1 - 43)
        self.canvas.itemconfigure(
            self.switch_position_text_tag,
            text=(definition.positions[self.switch_position - 1].name
                  if switch_type.startswith("custom:")
                  else f"P{self.switch_position}/{max_position}"),
        )
        self._end_visual_update(rotation)

    def active_switch_groups(self) -> dict[str, set[str]]:
        """Return isolated A-side and B-side active contact groups for simulation."""
        if self.properties["switch_type"] == "toggle_3way":
            groups: dict[str, set[str]] = {}
            if {"A", "A_prime"} <= self.active_switch_terminals:
                groups["A"] = {"A", "A_prime"}
            if {"B", "B_prime"} <= self.active_switch_terminals:
                groups["B"] = {"B", "B_prime"}
            return groups
        if self.properties["switch_type"].startswith("custom:"):
            definition = CUSTOM_SWITCH_DEFINITIONS[
                self.properties["switch_type"].removeprefix("custom:")
            ]
            return {
                f"group_{index}": set(group)
                for index, group in enumerate(
                    definition.positions[self.switch_position - 1].connections
                )
            }
        return {
            "A": {name for name in self.active_switch_terminals if name.startswith("A")},
            "B": {name for name in self.active_switch_terminals if name.startswith("B")},
        }

    def electrical_terminals(self) -> dict[str, int]:
        if self.kind == "switch" and self.properties["switch_type"].startswith("custom:"):
            return {
                name.removeprefix("custom_"): item
                for name, item in self.terminals.items()
                if name.startswith("custom_")
            }
        if self.kind == "switch" and self.properties["switch_type"] == "toggle_3way":
            return {
                name.removeprefix("toggle_"): item
                for name, item in self.terminals.items()
                if name.startswith("toggle_")
            }
        if self.kind != "pickup":
            return dict(self.terminals)
        if self.properties["pickup_type"] == "humbucker":
            return {
                name: item
                for name, item in self.terminals.items()
                if name.startswith("north_") or name.startswith("south_")
            }
        return {
            "hot": self.terminals["single_hot"],
            "gnd": self.terminals["single_gnd"],
        }





    def move(self, dx: float, dy: float) -> None:
        self.canvas.move(self.tag, dx, dy)
        if self.hitbox_bounds is not None:
            x1, y1, x2, y2 = self.hitbox_bounds
            self.hitbox_bounds = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        self._position_rotation_controls()

    def contains_point(self, x: float, y: float) -> bool:
        if self.hitbox_bounds is None:
            return False
        x1, y1, x2, y2 = self.hitbox_bounds
        return x1 <= x <= x2 and y1 <= y <= y2

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.canvas.itemconfigure(self.selection_tag, state="normal" if selected else "hidden")
        self.canvas.itemconfigure(
            f"rotation_controls_{self.component_id}",
            state="normal" if selected else "hidden",
        )
        self.canvas.itemconfigure(
            self.rename_control_tag,
            state="normal" if selected else "hidden",
        )
        if selected:
            self.canvas.tag_raise(f"rotation_controls_{self.component_id}")
            self.canvas.tag_raise(self.rename_control_tag)

    def set_external_text_visible(self, visible: bool) -> None:
        state = "normal" if visible else "hidden"
        self.canvas.itemconfigure(self.label_tag, state=state)
        self.canvas.itemconfigure(self.detail_tag, state=state)

    def delete(self) -> None:
        self.canvas.delete(self.tag)
