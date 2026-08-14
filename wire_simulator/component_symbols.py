from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .custom_switches import CustomSwitchDefinition


class ComponentSymbolRenderer:
    """Canvas drawing primitives for built-in component symbols."""

    def _draw_pickup_symbol(self, x1: float, x2: float, x: float, y: float) -> None:
        bar_left, bar_right = x1 + 16, x2 - 16
        single_tags = ("component", "component_body", self.pickup_single_tag, self.tag)
        self.canvas.create_line(
            bar_left, y, bar_right, y, fill="#111827", width=30,
            capstyle="round", tags=single_tags,
        )
        self.canvas.create_line(
            bar_left, y, bar_right, y, fill="#ffffff", width=23,
            capstyle="round", tags=single_tags,
        )
        humbucker_tags = ("component", "component_body", self.pickup_humbucker_tag, self.tag)
        for coil_y in (y - 11, y + 11):
            self.canvas.create_line(
                bar_left, coil_y, bar_right, coil_y, fill="#111827", width=23,
                capstyle="round", tags=humbucker_tags,
            )
            self.canvas.create_line(
                bar_left, coil_y, bar_right, coil_y, fill="#ffffff", width=16,
                capstyle="round", tags=humbucker_tags,
            )
        single_terminal_y = y + 28
        for terminal_name, terminal_x, color in (
            ("single_hot", x - 13, "#ef4444"),
            ("single_gnd", x + 13, "#111827"),
        ):
            terminal = self.canvas.create_oval(
                terminal_x - 7, single_terminal_y - 7,
                terminal_x + 7, single_terminal_y + 7,
                fill=color, outline="#202936", width=2,
                tags=("component", "terminal", self.pickup_single_tag, self.tag),
            )
            self.terminals[terminal_name] = terminal

        humbucker_terminal_y = y + 34
        humbucker_terminals = (
            ("north_hot", x - 33, "N", "#ef4444"),
            ("north_gnd", x - 11, "N", "#111827"),
            ("south_hot", x + 11, "S", "#ef4444"),
            ("south_gnd", x + 33, "S", "#111827"),
        )
        for terminal_name, terminal_x, coil_label, terminal_color in humbucker_terminals:
            terminal = self.canvas.create_oval(
                terminal_x - 8, humbucker_terminal_y - 8,
                terminal_x + 8, humbucker_terminal_y + 8,
                fill=terminal_color, outline="#202936", width=2,
                tags=("component", "terminal", self.pickup_humbucker_tag, self.tag),
            )
            self.terminals[terminal_name] = terminal
            self.canvas.create_text(
                terminal_x, humbucker_terminal_y, text=coil_label,
                fill="#ffffff", font=("Arial", 8, "bold"),
                tags=("component", "terminal_label", self.pickup_humbucker_tag, self.tag),
            )

    def _draw_potentiometer_symbol(self, x: float, y: float) -> None:
        resistor_y = y - 7.2
        track_left, track_right = x - 30.4, x + 30.4
        self.canvas.create_rectangle(
            track_left - 3.2, resistor_y - 11.2,
            track_right + 3.2, resistor_y + 11.2,
            fill="", outline="",
            tags=("component", self.gauge_track_tag, self.tag),
        )
        self.canvas.create_line(
            x - 44, resistor_y, track_left, resistor_y,
            fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        zigzag: list[float] = [track_left, resistor_y]
        step = (track_right - track_left) / 10
        for index in range(1, 10):
            zigzag.extend(
                (track_left + step * index, resistor_y + (-7.2 if index % 2 else 7.2))
            )
        zigzag.extend((track_right, resistor_y))
        self.canvas.create_line(
            *zigzag, fill="#202936", width=3, joinstyle="miter",
            tags=("component", "component_body", self.tag),
        )
        self.canvas.create_line(
            track_right, resistor_y, x + 44, resistor_y,
            fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        self.canvas.create_line(
            x, y + 35.2, x, y + 18.4, x, y + 18.4, x, resistor_y + 3.2,
            fill="#2563eb", width=3, arrow="last", arrowshape=(10, 12, 5),
            tags=("component", "component_body", self.gauge_fill_tag, self.tag),
        )
        for terminal_name, end_x, end_y in (
            ("1", x - 44, resistor_y),
            ("2", x, y + 35.2),
            ("3", x + 44, resistor_y),
        ):
            terminal = self.canvas.create_oval(
                end_x - 7, end_y - 7, end_x + 7, end_y + 7,
                fill="#f8fafc", outline="#202936", width=2,
                tags=("component", "terminal", self.tag),
            )
            self.terminals[terminal_name] = terminal
            label_x = end_x if terminal_name != "2" else end_x + 14
            label_y = end_y - 14 if terminal_name != "2" else end_y
            self.canvas.create_text(
                label_x, label_y, text=terminal_name, fill="#202936",
                font=("Arial", 8, "bold"),
                tags=("component", "terminal_label", self.tag),
            )
        self.canvas.create_text(
            x + 44, y + 33.6, text="50", fill="#2563eb",
            font=("Arial", 9, "bold"),
            tags=("component", "component_body", self.gauge_text_tag, self.tag),
        )
        self.set_gauge_value(self.gauge_value)

    def _draw_jack_symbol(self, x: float, y: float) -> None:
        for radius, width in ((27, 4), (15, 3)):
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill="#ffffff" if radius == 27 else "",
                outline="#202936", width=width,
                tags=("component", "component_body", self.tag),
            )

        jack_tips = (
            (x + 20, y - 18, x + 50, y - 31, "#ef4444", "Hot"),
            (x + 11, y + 10, x + 50, y + 28, "#111827", "GND"),
        )
        for terminal_name, (start_x, start_y, end_x, end_y, color, terminal_label) in zip(
            ("hot", "gnd"), jack_tips
        ):
            self.canvas.create_line(
                start_x, start_y, end_x, end_y, fill=color, width=4,
                tags=("component", "component_body", self.tag),
            )
            terminal = self.canvas.create_oval(
                end_x - 7, end_y - 7, end_x + 7, end_y + 7,
                fill=color, outline="#202936", width=2,
                tags=("component", "terminal", self.tag),
            )
            self.terminals[terminal_name] = terminal
            label_item = self.canvas.create_text(
                end_x - 13, end_y, text=terminal_label, anchor="e",
                fill="#202936", font=("Arial", 8, "bold"),
                tags=("component", "terminal_label", self.tag),
            )
            self.external_terminal_labels[terminal_name] = label_item

    def _draw_ground_symbol(self, x: float, y: float) -> None:
        terminal_y = y - 24
        terminal = self.canvas.create_oval(
            x - 7, terminal_y - 7, x + 7, terminal_y + 7,
            fill="#111827", outline="#202936", width=2,
            tags=("component", "terminal", self.tag),
        )
        self.terminals["gnd"] = terminal
        self.canvas.create_line(
            x, terminal_y + 7, x, y + 2, fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        for line_y, half_width in ((y + 3, 22), (y + 11, 15), (y + 19, 8)):
            self.canvas.create_line(
                x - half_width, line_y, x + half_width, line_y,
                fill="#202936", width=3,
                tags=("component", "component_body", self.tag),
            )

    def _draw_blade_switch_symbol(self, x: float, y: float) -> None:
        self.canvas.create_rectangle(
            x - 17, y - 72, x + 17, y + 72,
            fill="#d1d5db", outline="#202936", width=3,
            tags=("component", "component_body", self.switch_track_tag,
                  self.blade_symbol_tag, self.tag),
        )
        terminal_rows = (-54, -18, 18, 54)
        a_labels = ("A1", "A2", "A3", "A0")
        b_labels = ("B0", "B1", "B2", "B3")
        for row_y, a_label, b_label in zip(terminal_rows, a_labels, b_labels):
            absolute_y = y + row_y
            for side, terminal_x, label, color in (
                ("A", x - 38, a_label, "#16a34a"),
                ("B", x + 38, b_label, "#ea580c"),
            ):
                terminal = self.canvas.create_oval(
                    terminal_x - 7, absolute_y - 7,
                    terminal_x + 7, absolute_y + 7,
                    fill="#ffffff", outline=color, width=3,
                    tags=(
                        "component", "terminal", f"switch_side_{side}",
                        f"switch_terminal_{label}_{self.component_id}",
                        self.blade_symbol_tag, self.tag,
                    ),
                )
                self.terminals[label] = terminal
                label_x = terminal_x - 12 if side == "A" else terminal_x + 12
                label_item = self.canvas.create_text(
                    label_x, absolute_y, text=label,
                    anchor="e" if side == "A" else "w",
                    fill=color, font=("Arial", 9, "bold"),
                    tags=("component", "terminal_label", self.blade_symbol_tag, self.tag),
                )
                self.external_terminal_labels[label] = label_item
        self.canvas.create_text(
            x, y + 84, text="P1", fill="#202936",
            font=("Arial", 10, "bold"),
            tags=("component", self.switch_position_text_tag,
                  self.blade_symbol_tag, self.tag),
        )

    def _draw_resistor_symbol(self, x1: float, x2: float, x: float, y: float) -> None:
        symbol_left, symbol_right = x - 19, x + 19
        self.canvas.create_line(
            x1, y, symbol_left, y, fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        points: list[float] = [symbol_left, y]
        step = (symbol_right - symbol_left) / 8
        for index in range(1, 8):
            points.extend((symbol_left + step * index, y + (-9 if index % 2 else 9)))
        points.extend((symbol_right, y))
        self.canvas.create_line(
            *points, fill="#202936", width=3, joinstyle="miter",
            tags=("component", "component_body", self.tag),
        )
        self.canvas.create_line(
            symbol_right, y, x2, y, fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )

    def _draw_capacitor_symbol(self, x1: float, x2: float, x: float, y: float) -> None:
        plate_gap = 4
        self.canvas.create_line(
            x1, y, x - plate_gap, y, fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        self.canvas.create_line(
            x + plate_gap, y, x2, y, fill="#202936", width=3,
            tags=("component", "component_body", self.tag),
        )
        for plate_x in (x - plate_gap, x + plate_gap):
            self.canvas.create_line(
                plate_x, y - 12, plate_x, y + 12, fill="#202936", width=4,
                tags=("component", "component_body", self.tag),
            )
    def _draw_toggle_switch_symbol(self, x: float, y: float) -> None:
        common_tags = ("component", "component_body", self.toggle_symbol_tag, self.tag)
        self.canvas.create_oval(
            x - 27, y - 30, x + 27, y + 24,
            fill="#e5e7eb", outline="#202936", width=3, tags=common_tags,
        )
        self.canvas.create_oval(
            x - 10, y - 13, x + 10, y + 7,
            fill="#ffffff", outline="#202936", width=3, tags=common_tags,
        )
        self.canvas.create_line(
            x, y - 3, x - 18, y - 46, fill="#202936", width=6,
            capstyle="round",
            tags=("component", "component_body", self.toggle_symbol_tag,
                  self.toggle_lever_tag, self.tag),
        )
        terminal_specs = (
            ("A", x - 58, y - 27, "A", "#16a34a"),
            ("A_prime", x - 58, y + 27, "A′", "#16a34a"),
            ("B", x + 58, y - 27, "B", "#ea580c"),
            ("B_prime", x + 58, y + 27, "B′", "#ea580c"),
            ("gnd", x, y + 72, "G", "#111827"),
        )
        for name, terminal_x, terminal_y, label, color in terminal_specs:
            terminal = self.canvas.create_oval(
                terminal_x - 7, terminal_y - 7, terminal_x + 7, terminal_y + 7,
                fill="#ffffff", outline=color, width=3,
                tags=("component", "terminal", f"toggle_terminal_{name}_{self.component_id}",
                      self.toggle_symbol_tag, self.tag),
            )
            self.terminals[f"toggle_{name}"] = terminal
            is_left = terminal_x < x
            is_right = terminal_x > x
            label_item = self.canvas.create_text(
                terminal_x + (-14 if is_left else 14 if is_right else 0),
                terminal_y if name != "gnd" else terminal_y + 15,
                text=label, fill=color, font=("Arial", 9, "bold"),
                anchor="e" if is_left else "w" if is_right else "center",
                tags=("component", "terminal_label", self.toggle_symbol_tag, self.tag),
            )
            self.external_terminal_labels[f"toggle_{name}"] = label_item
        self.canvas.create_line(
            x - 58, y - 20, x - 58, y + 20,
            fill="#16a34a", width=5, state="hidden",
            tags=("component", "component_body", self.toggle_symbol_tag,
                  f"toggle_connection_A_{self.component_id}", self.tag),
        )
        self.canvas.create_line(
            x + 58, y - 20, x + 58, y + 20,
            fill="#ea580c", width=5, state="hidden",
            tags=("component", "component_body", self.toggle_symbol_tag,
                  f"toggle_connection_B_{self.component_id}", self.tag),
        )
        self.canvas.create_text(
            x, y + 50, text="P1/3", fill="#202936", font=("Arial", 10, "bold"),
            tags=("component", self.switch_position_text_tag,
                  self.toggle_symbol_tag, self.tag),
        )
        self.canvas.itemconfigure(self.toggle_symbol_tag, state="hidden")
    def _clear_custom_switch(self) -> None:
        self.canvas.delete(self.custom_symbol_tag)
        for name in [name for name in self.terminals if name.startswith("custom_")]:
            del self.terminals[name]
        self.custom_switch_definition = None
        self.custom_switch_center = None

    def _show_custom_switch(self, definition: CustomSwitchDefinition) -> None:
        if self.custom_switch_definition is definition:
            self.canvas.itemconfigure(self.custom_symbol_tag, state="normal")
            return
        self._clear_custom_switch()
        if self.hitbox_bounds is None:
            return
        x1, y1, x2, y2 = self.hitbox_bounds
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        symbol_width = max(84, (definition.columns - 1) * 36 + 68)
        symbol_height = max(76, (definition.rows - 1) * 36 + 68)
        self._set_switch_visual_bounds(symbol_width, symbol_height)
        self.custom_switch_definition = definition
        self.custom_switch_center = (x, y)
        tags = ("component", "component_body", self.custom_symbol_tag, self.tag)
        self.canvas.create_rectangle(
            x - symbol_width / 2 + 18, y - symbol_height / 2 + 18,
            x + symbol_width / 2 - 18, y + symbol_height / 2 - 18,
            fill="#e5e7eb", outline="#202936", width=3, tags=tags,
        )
        terminal_visual_tag = f"custom_terminal_visual_{self.component_id}"
        for terminal in definition.terminals:
            terminal_x = x + (terminal.column - (definition.columns - 1) / 2) * 36
            terminal_y = y + (terminal.row - (definition.rows - 1) / 2) * 36
            item = self.canvas.create_oval(
                terminal_x - 8, terminal_y - 8, terminal_x + 8, terminal_y + 8,
                fill="#ffffff", outline="#6d28d9", width=3,
                tags=("component", "terminal", terminal_visual_tag,
                      self.custom_symbol_tag, self.tag),
            )
            self.terminals[f"custom_{terminal.terminal_id}"] = item
            self.canvas.create_text(
                terminal_x, terminal_y, text=terminal.terminal_id,
                fill="#202936", font=("Arial", 7, "bold"),
                tags=("component", "terminal_label", terminal_visual_tag,
                      self.custom_symbol_tag, self.tag),
            )
        self.canvas.create_text(
            x, y, text=definition.name, width=max(45, symbol_width - 52),
            fill="#6b7280", font=("Malgun Gothic", 7),
            tags=("component", "terminal_label", self.custom_symbol_tag, self.tag),
        )
        self.canvas.create_text(
            x, y + symbol_height / 2 - 10, text="", fill="#202936",
            font=("Arial", 9, "bold"),
            tags=("component", self.switch_position_text_tag,
                  self.custom_symbol_tag, self.tag),
        )

    def _draw_custom_connections(self, connections: tuple[tuple[str, ...], ...]) -> None:
        self.canvas.delete(self.custom_connection_tag)
        if self.custom_switch_center is None:
            return
        for group in connections:
            points: list[float] = []
            for terminal_id in group:
                item = self.terminals[f"custom_{terminal_id}"]
                x1, y1, x2, y2 = self.canvas.coords(item)
                points.extend(((x1 + x2) / 2, (y1 + y2) / 2))
                self.canvas.itemconfigure(item, fill="#f59e0b")
            if len(points) >= 4:
                self.canvas.create_line(
                    *points, fill="#7c3aed", width=5,
                    tags=("component", "component_body", self.custom_symbol_tag,
                          self.custom_connection_tag, self.tag),
                )
        active = {terminal for group in connections for terminal in group}
        for terminal in self.custom_switch_definition.terminals:
            self.canvas.itemconfigure(
                self.terminals[f"custom_{terminal.terminal_id}"],
                fill="#f59e0b" if terminal.terminal_id in active else "#ffffff",
            )
        self.canvas.tag_raise(f"custom_terminal_visual_{self.component_id}")

    def _set_switch_visual_bounds(self, width: float, height: float) -> None:
        if self.hitbox_bounds is None:
            return
        x1, y1, x2, y2 = self.hitbox_bounds
        x, y = (x1 + x2) / 2, (y1 + y2) / 2
        self.hitbox_bounds = (
            x - width / 2 - 7, y - height / 2 - 5,
            x + width / 2 + 7, y + height / 2 + 5,
        )
        for item in self.canvas.find_withtag(self.tag):
            if "component_hitbox" in self.canvas.gettags(item):
                self.canvas.coords(item, *self.hitbox_bounds)
                break
        self.canvas.coords(
            self.selection_tag,
            x - width / 2 - 7, y - height / 2 - 5,
            x + width / 2 + 7, y + height / 2 + 5,
        )
        self.canvas.coords(self.label_tag, x, y - height / 2 - 12)
        self.canvas.coords(self.detail_tag, x, y + height / 2 + 14)
        self._position_rotation_controls()
