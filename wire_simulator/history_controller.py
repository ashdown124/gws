from __future__ import annotations

import copy
import tkinter as tk

from .editor_models import HistoryEntry


class HistoryControllerMixin:
    """Undo/redo state and presentation for the simulator application."""

    def _commit_history(self, action: str, before: dict[str, object]) -> None:
        if self.history_restoring:
            return
        after = self._diagram_data()
        if before == after:
            return
        self.undo_history.append(HistoryEntry(action, copy.deepcopy(before), after))
        if len(self.undo_history) > self.HISTORY_LIMIT:
            del self.undo_history[0]
        self.redo_history.clear()
        self._update_history_button_states()
        self._refresh_document_state()

    def _update_history_button_states(self) -> None:
        if not hasattr(self, "undo_button"):
            return
        self.undo_button.configure(state="normal" if self.undo_history else "disabled")
        self.redo_button.configure(state="normal" if self.redo_history else "disabled")
        self._refresh_history_list()

    def _refresh_history_list(self) -> None:
        if not hasattr(self, "history_list"):
            return
        self.history_list.delete(0, tk.END)
        timeline: list[tuple[HistoryEntry, bool]] = [
            *((entry, True) for entry in self.undo_history),
            *((entry, False) for entry in reversed(self.redo_history)),
        ]
        if not timeline:
            self.history_list.insert(tk.END, self.localization.text("history_empty"))
            self.history_list.itemconfigure(0, foreground="#7c8999")
            return
        for entry, applied in reversed(timeline[-self.HISTORY_LIMIT:]):
            action = self.localization.text(f"history_action_{entry.action}")
            target = self._history_entry_target(entry)
            if target:
                action = f"{action} · {target}"
            label = action if applied else self._strikethrough_text(action)
            self.history_list.insert(tk.END, label)
            if not applied:
                self.history_list.itemconfigure(tk.END, foreground="#7c8999")

    @staticmethod
    def _strikethrough_text(value: str) -> str:
        return "".join(
            character if character.isspace() else f"{character}\u0336"
            for character in value
        )

    def _history_entry_target(self, entry: HistoryEntry) -> str:
        before_components = {
            int(record["id"]): record
            for record in entry.before.get("components", []) if isinstance(record, dict)
        }
        after_components = {
            int(record["id"]): record
            for record in entry.after.get("components", []) if isinstance(record, dict)
        }
        component_id: int | None = None
        if entry.action in ("component_add", "component_copy"):
            component_id = next(iter(after_components.keys() - before_components.keys()), None)
        elif entry.action == "component_delete":
            component_id = next(iter(before_components.keys() - after_components.keys()), None)
        elif entry.action in (
            "component_move", "component_rotate", "component_rename", "option_change"
        ):
            component_id = next((
                item_id for item_id in before_components.keys() & after_components.keys()
                if before_components[item_id] != after_components[item_id]
            ), None)
        if component_id is not None:
            record = after_components.get(component_id) or before_components[component_id]
            kind = str(record["kind"])
            name = str(record.get("name", "")).strip()
            return f"{name or self.localization.text(f'component_{kind}')} #{component_id}"

        before_wires = {
            int(record["id"]): record
            for record in entry.before.get("wires", []) if isinstance(record, dict)
        }
        after_wires = {
            int(record["id"]): record
            for record in entry.after.get("wires", []) if isinstance(record, dict)
        }
        wire_id: int | None = None
        if entry.action == "wire_add":
            wire_id = next(iter(after_wires.keys() - before_wires.keys()), None)
        elif entry.action == "wire_delete":
            wire_id = next(iter(before_wires.keys() - after_wires.keys()), None)
        elif entry.action in (
            "wire_node_add", "wire_node_delete", "wire_node_move", "option_change"
        ):
            wire_id = next((
                item_id for item_id in before_wires.keys() & after_wires.keys()
                if before_wires[item_id] != after_wires[item_id]
            ), None)
        if wire_id is not None:
            return f"{self.localization.text('wire_label')} #{wire_id}"
        return ""

    def _restore_history_snapshot(self, snapshot: dict[str, object]) -> None:
        restored = copy.deepcopy(snapshot)
        current_controls = {
            component.component_id: (component.gauge_value, component.switch_position)
            for component in self.components.values()
        }
        for record in restored.get("components", []):
            if isinstance(record, dict) and record.get("id") in current_controls:
                gauge, switch_position = current_controls[int(record["id"])]
                record["gauge_value"] = gauge
                record["switch_position"] = switch_position
        self.history_restoring = True
        try:
            self._restore_diagram(restored)
            self.simulation_signature = None
        finally:
            self.history_restoring = False

    def undo(self) -> None:
        if not self.undo_history:
            return
        entry = self.undo_history.pop()
        self._restore_history_snapshot(entry.before)
        self.redo_history.append(entry)
        self._update_history_button_states()

    def _undo_shortcut(self, _event: tk.Event) -> str:
        self.undo()
        return "break"

    def redo(self) -> None:
        if not self.redo_history:
            return
        entry = self.redo_history.pop()
        self._restore_history_snapshot(entry.after)
        self.undo_history.append(entry)
        self._update_history_button_states()

    def _redo_shortcut(self, _event: tk.Event) -> str:
        self.redo()
        return "break"

    def _reset_history(self) -> None:
        self.undo_history.clear()
        self.redo_history.clear()
        self._update_history_button_states()
