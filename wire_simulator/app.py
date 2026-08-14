from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .components import (
    COMPONENT_STYLES,
    CanvasComponent,
    configure_custom_switches,
)
from .canvas_scene import CanvasSceneMixin
from .custom_switches import (
    CustomSwitchDefinition,
    CustomSwitchLoadError,
    load_custom_switches,
)
from .diagram_controller import DiagramControllerMixin
from .element_panel import ElementPanelMixin
from .history_controller import HistoryControllerMixin
from .canvas_interaction import CanvasInteractionMixin
from .localization import Localization
from .editor_models import HistoryEntry, WireConnection
from .properties_panel import PropertiesPanelMixin
from .circuit_simulation import CircuitSimulator, SignalSimulationState
from .simulation_panel import SimulationPanelMixin
from .app_ui import AppUIMixin
from .wiring_controller import WiringControllerMixin


class WireSimulatorApp(
    AppUIMixin, CanvasInteractionMixin, DiagramControllerMixin,
    CanvasSceneMixin, WiringControllerMixin, ElementPanelMixin,
    PropertiesPanelMixin, SimulationPanelMixin, HistoryControllerMixin,
):
    GRID_SIZE = 24
    HISTORY_LIMIT = 50

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.app_icon: tk.PhotoImage | None = None
        icon_path = Path(__file__).resolve().parent / "assets" / "app" / "gws_icon.png"
        try:
            self.app_icon = tk.PhotoImage(master=self.root, file=str(icon_path))
            self.root.iconphoto(True, self.app_icon)
        except tk.TclError:
            self.app_icon = None
        self.root.geometry("1420x800")
        self.root.minsize(1100, 720)
        self.root.configure(bg="#18202b")
        self.localization = Localization()
        self.custom_switches: dict[str, CustomSwitchDefinition] = {}
        custom_switch_errors: list[CustomSwitchLoadError] = []
        try:
            self.custom_switches = load_custom_switches(errors=custom_switch_errors)
        except OSError as error:
            messagebox.showerror(
                self.localization.text("custom_switch_error_title"),
                self.localization.text("custom_switch_error_message").format(error=error),
                parent=self.root,
            )
        if custom_switch_errors:
            error_details = "\n".join(
                f"- {error.source_path.name}: {error.message}"
                for error in custom_switch_errors
            )
            messagebox.showwarning(
                self.localization.text("custom_switch_error_title"),
                self.localization.text("custom_switch_error_message").format(
                    error=error_details
                ),
                parent=self.root,
            )
        configure_custom_switches(self.custom_switches)
        self.components: dict[str, CanvasComponent] = {}
        self.next_component_id = 1
        self.next_wire_id = 1
        self.selected_tag: str | None = None
        self.selected_tags: set[str] = set()
        self.drag_origin: tuple[float, float] | None = None
        self.selected_component_kind = next(iter(COMPONENT_STYLES))
        self.element_list_tags: list[str] = []
        self.wire_list_references: list[str] = []
        self.wires: list[WireConnection] = []
        self.wire_start_endpoint: int | None = None
        self.wire_nodes: list[tuple[float, float]] = []
        self.wire_cursor: tuple[float, float] | None = None
        self.wire_preview_items: list[int] = []
        self.selected_wire: WireConnection | None = None
        self.selected_wire_node: tuple[WireConnection, int] | None = None
        self.dragged_wire_node: tuple[WireConnection, int] | None = None
        self.pending_wire_node_item: int | None = None
        self.node_drag_started = False
        self.drag_history_before: dict[str, object] | None = None
        self.undo_history: list[HistoryEntry] = []
        self.redo_history: list[HistoryEntry] = []
        self.history_restoring = False
        self.simulation = SignalSimulationState()
        self.circuit_simulator = CircuitSimulator()
        self.simulation_job: str | None = None
        self.simulation_signature: tuple[object, ...] | None = None
        self.pickup_trace_vars: dict[str, tk.BooleanVar] = {}
        self.show_component_labels = tk.BooleanVar(value=True)
        self.current_diagram_path: str | None = None
        self.saved_diagram_snapshot: dict[str, object] | None = None
        self._configure_style()
        self._build_ui()
        self._bind_events()
        self._apply_language()
        self._mark_diagram_clean()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after_idle(self._run_signal_simulation)

    def _apply_language(self) -> None:
        text = self.localization.text
        self._refresh_window_title()
        self.language_label.configure(text=text("language_label"))
        self.palette_title.configure(text=text("palette_title"))
        self.palette_hint.configure(text=text("palette_hint"))
        self.component_select_label.configure(text=text("component_select"))
        self.add_component_button.configure(text=text("add_component"))
        self.save_button.configure(text=text("save_diagram"))
        self.load_button.configure(text=text("load_diagram"))
        self.delete_button.configure(text=text("delete_selected"))
        self.undo_button.configure(text=text("undo"))
        self.redo_button.configure(text=text("redo"))
        self.history_title.configure(text=text("history_title"))
        self.clear_button.configure(text=text("clear_all"))
        self.controls_help_button.configure(text=text("controls_help_button"))
        self.elements_title.configure(text=text("components_title"))
        self.show_component_labels_check.configure(text=text("show_component_labels"))
        self.wires_title.configure(text=text("wires_title"))
        self.move_up_button.configure(text=text("move_up"))
        self.move_down_button.configure(text=text("move_down"))
        self.properties_title.configure(text=text("properties_title"))
        self.canvas.itemconfigure(self.wire_mode_indicator, text=text("wire_mode"))
        self.simulation_title.configure(text=text("simulation_title"))
        self.pickup_traces_title.configure(text=text("pickup_traces_title"))
        self.magnitude_spectrum_title.configure(text=text("magnitude_spectrum_title"))
        self.phase_spectrum_title.configure(text=text("phase_spectrum_title"))
        self.simulation_note.configure(text=text("simulation_note"))
        self._refresh_simulation_panel()
        component_names = [text(f"component_{kind}") for kind in COMPONENT_STYLES]
        self.component_choice.configure(values=component_names)
        selected_index = list(COMPONENT_STYLES).index(self.selected_component_kind)
        self.component_choice.current(selected_index)
        for component in self.components.values():
            component.set_custom_name(
                component.custom_name, text(f"component_{component.kind}")
            )
            component.set_detail(self._component_detail(component))
        self._refresh_element_list()
        self._render_property_editor()
        self._update_history_button_states()
        self._update_status_bar()

    def _mark_diagram_clean(self, path: str | None = None) -> None:
        self.current_diagram_path = path
        self.saved_diagram_snapshot = self._diagram_data()
        self._refresh_document_state()

    def _document_is_dirty(self) -> bool:
        return (
            self.saved_diagram_snapshot is not None
            and self._diagram_data() != self.saved_diagram_snapshot
        )

    def _refresh_document_state(self) -> None:
        if not hasattr(self, "status_bar"):
            return
        self._refresh_window_title()
        self._update_status_bar()

    def _refresh_window_title(self) -> None:
        application_title = self.localization.text("window_title")
        if self.saved_diagram_snapshot is not None and self._document_is_dirty():
            application_title = f"{application_title} *"
        title = application_title
        if self.current_diagram_path:
            title = f"{Path(self.current_diagram_path).name} - {application_title}"
        self.root.title(title)

    def _update_status_bar(self) -> None:
        if not hasattr(self, "status_bar"):
            return
        text = self.localization.text
        sections = [
            Path(self.current_diagram_path).name
            if self.current_diagram_path else text("status_untitled"),
            text("status_modified") if self._document_is_dirty() else text("status_saved"),
        ]
        if self.wire_start_endpoint is not None:
            sections.append(text("status_wiring"))
        elif self.selected_wire is not None:
            sections.append(text("status_selected_wire").format(id=self.selected_wire.wire_id))
        elif len(self.selected_tags) > 1:
            sections.append(text("status_selected_multiple").format(
                count=len(self.selected_tags)
            ))
        elif self.selected_tag in self.components:
            component = self.components[self.selected_tag]
            sections.append(text("status_selected_component").format(
                name=component.custom_name or text(f"component_{component.kind}"),
                id=component.component_id,
            ))
        else:
            sections.append(text("status_no_selection"))
        self.status_bar.configure(text="  |  ".join(sections))

    def _confirm_discard_unsaved(self) -> bool:
        if not self._document_is_dirty():
            return True
        return messagebox.askyesno(
            self.localization.text("unsaved_title"),
            self.localization.text("unsaved_message"),
            parent=self.root,
        )

    def _on_close(self) -> None:
        if self._confirm_discard_unsaved():
            self.root.destroy()

    def _show_controls_help(self) -> None:
        messagebox.showinfo(
            self.localization.text("controls_help_title"),
            self.localization.text("instructions"),
            parent=self.root,
        )

    def _change_language(self, _event: tk.Event) -> None:
        self.localization.select_by_name(self.language_choice.get())
        self._apply_language()

    def _select_component_kind(self, _event: tk.Event) -> None:
        selected_index = self.component_choice.current()
        if selected_index >= 0:
            self.selected_component_kind = list(COMPONENT_STYLES)[selected_index]
        self._update_add_component_button_state()

    def _add_selected_component(self) -> None:
        self.add_component(self.selected_component_kind)

    def run(self) -> None:
        self.root.mainloop()
