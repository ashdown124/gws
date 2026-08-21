from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class AppUIMixin:
    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Sidebar.TFrame", background="#202936")
        style.configure("Title.TLabel", background="#202936", foreground="#f8fafc",
                        font=("Malgun Gothic", 16, "bold"))
        style.configure("Hint.TLabel", background="#202936", foreground="#a9b4c3",
                        font=("Malgun Gothic", 9))
        style.configure(
            "SpectrumTitle.TLabel",
            background="#202936",
            foreground="#cbd5e1",
            font=("Malgun Gothic", 10, "bold"),
        )
        style.configure(
            "SpectrumControl.TButton",
            font=("Malgun Gothic", 8),
            padding=(4, 2),
        )
        style.configure("Component.TButton", font=("Malgun Gothic", 10), padding=(10, 9))
        style.configure(
            "Sidebar.TCheckbutton", background="#202936", foreground="#e7edf5",
            font=("Malgun Gothic", 9),
        )
        style.map(
            "Sidebar.TCheckbutton",
            background=[("active", "#202936")],
            foreground=[("disabled", "#64748b"), ("!disabled", "#e7edf5")],
        )
        style.configure(
            "NewDiagram.TButton",
            font=("Malgun Gothic", 10, "bold"),
            padding=(10, 9),
            foreground="#0f172a",
            background="#38bdf8",
            bordercolor="#0284c7",
        )
        style.map(
            "NewDiagram.TButton",
            background=[("active", "#7dd3fc"), ("pressed", "#0ea5e9")],
            foreground=[("disabled", "#64748b"), ("!disabled", "#0f172a")],
        )

    def _build_ui(self) -> None:
        sidebar = ttk.Frame(self.root, width=240, style="Sidebar.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        language_row = ttk.Frame(sidebar, style="Sidebar.TFrame")
        language_row.pack(fill="x", padx=18, pady=(18, 4))
        self.language_label = ttk.Label(language_row, style="Hint.TLabel")
        self.language_label.pack(side="left")
        self.language_choice = ttk.Combobox(
            language_row, values=self.localization.choices(), state="readonly", width=12
        )
        self.language_choice.pack(side="right")
        self.language_choice.set(self.localization.text("language_name"))
        self.language_choice.bind("<<ComboboxSelected>>", self._change_language)

        self.palette_title = ttk.Label(sidebar, style="Title.TLabel")
        self.palette_title.pack(anchor="w", padx=18, pady=(12, 8))
        self.palette_hint = ttk.Label(sidebar, style="Hint.TLabel", justify="left")
        self.palette_hint.pack(anchor="w", padx=18, pady=(0, 18))

        self.component_select_label = ttk.Label(sidebar, style="Hint.TLabel")
        self.component_select_label.pack(anchor="w", padx=18, pady=(0, 5))
        self.component_choice = ttk.Combobox(sidebar, state="readonly")
        self.component_choice.pack(fill="x", padx=16, pady=(0, 8))
        self.component_choice.bind("<<ComboboxSelected>>", self._select_component_kind)
        self.add_component_button = ttk.Button(
            sidebar, style="Component.TButton", command=self._add_selected_component
        )
        self.add_component_button.pack(fill="x", padx=16, pady=5)
        self.delete_button = ttk.Button(sidebar, command=self.delete_selected)
        self.delete_button.pack(fill="x", padx=16, pady=5)

        ttk.Separator(sidebar).pack(fill="x", padx=16, pady=18)
        self.save_button = ttk.Button(sidebar, command=self._save_diagram)
        self.save_button.pack(fill="x", padx=16, pady=5)
        self.load_button = ttk.Button(sidebar, command=self._load_diagram)
        self.load_button.pack(fill="x", padx=16, pady=5)
        self.history_title = ttk.Label(sidebar, style="Hint.TLabel")
        self.history_title.pack(anchor="w", padx=18, pady=(8, 4))
        self.history_list = tk.Listbox(
            sidebar,
            height=3,
            bg="#18202b",
            fg="#dbe4ef",
            selectbackground="#334155",
            selectforeground="#f8fafc",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            exportselection=False,
            font=("Malgun Gothic", 9),
        )
        self.history_list.pack(fill="x", padx=16, pady=(0, 5))
        history_buttons = ttk.Frame(sidebar, style="Sidebar.TFrame")
        history_buttons.pack(fill="x", padx=16, pady=(0, 5))
        self.undo_button = ttk.Button(history_buttons, command=self.undo)
        self.undo_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.redo_button = ttk.Button(history_buttons, command=self.redo)
        self.redo_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        sidebar_footer = ttk.Frame(sidebar, style="Sidebar.TFrame")
        sidebar_footer.pack(side="bottom", fill="x")
        self.new_diagram_button = ttk.Button(
            sidebar_footer,
            style="NewDiagram.TButton",
            command=self._confirm_new_diagram,
        )
        self.new_diagram_button.pack(fill="x", padx=16, pady=(5, 0))
        self.controls_help_button = ttk.Button(
            sidebar_footer, command=self._show_controls_help
        )
        self.controls_help_button.pack(fill="x", padx=16, pady=(10, 18))

        self.simulation_panel = ttk.Frame(self.root, width=250, style="Sidebar.TFrame")
        self.simulation_panel.pack(side="right", fill="y")
        self.simulation_panel.pack_propagate(False)
        self.simulation_title = ttk.Label(self.simulation_panel, style="Title.TLabel")
        self.simulation_title.pack(anchor="w", padx=16, pady=(22, 12))
        self.cable_capacitance_label = ttk.Label(
            self.simulation_panel, style="Hint.TLabel"
        )
        self.cable_capacitance_label.pack(anchor="w", padx=16, pady=(0, 4))
        cable_capacitance_row = ttk.Frame(
            self.simulation_panel, style="Sidebar.TFrame"
        )
        cable_capacitance_row.pack(fill="x", padx=16)
        self.cable_capacitance_entry = ttk.Entry(
            cable_capacitance_row,
            width=10,
            textvariable=self.cable_capacitance_var,
        )
        self.cable_capacitance_entry.pack(side="left")
        self.cable_capacitance_entry.bind(
            "<Return>", self._apply_cable_capacitance
        )
        ttk.Label(
            cable_capacitance_row, text="pF", style="Hint.TLabel"
        ).pack(side="left", padx=(6, 0))
        self.pickup_traces_title = ttk.Label(
            self.simulation_panel, style="Hint.TLabel"
        )
        self.pickup_traces_title.pack(anchor="w", padx=16, pady=(10, 3))
        self.pickup_traces_frame = ttk.Frame(
            self.simulation_panel, style="Sidebar.TFrame"
        )
        self.pickup_traces_frame.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Separator(self.simulation_panel).pack(fill="x", padx=16, pady=(0, 14))
        self.magnitude_spectrum_title = ttk.Label(
            self.simulation_panel, style="SpectrumTitle.TLabel"
        )
        self.magnitude_spectrum_title.pack(anchor="w", padx=16, pady=(0, 4))
        spectrum_scale_row = ttk.Frame(
            self.simulation_panel, style="Sidebar.TFrame"
        )
        spectrum_scale_row.pack(fill="x", padx=16, pady=(0, 4))
        self.spectrum_scale_label = ttk.Label(
            spectrum_scale_row, style="Hint.TLabel"
        )
        self.spectrum_scale_label.pack(side="left")
        self.spectrum_scale_choice = ttk.Combobox(
            spectrum_scale_row,
            width=7,
            state="readonly",
            textvariable=self.spectrum_scale_var,
            values=("Linear", "Log"),
        )
        self.spectrum_scale_choice.pack(side="right")
        self.spectrum_scale_choice.bind(
            "<<ComboboxSelected>>", self._change_spectrum_scale
        )
        self.reset_voltage_axis_button = ttk.Button(
            self.simulation_panel,
            style="SpectrumControl.TButton",
            command=self._reset_voltage_axis_max,
        )
        self.reset_voltage_axis_button.pack(
            anchor="w", padx=16, pady=(0, 6)
        )
        self.magnitude_spectrum = tk.Canvas(
            self.simulation_panel,
            height=190,
            bg="#111821",
            highlightthickness=1,
            highlightbackground="#394657",
        )
        self.magnitude_spectrum.pack(fill="x", padx=16, pady=(0, 12))
        self.phase_spectrum_title = ttk.Label(
            self.simulation_panel, style="SpectrumTitle.TLabel"
        )
        self.phase_spectrum_title.pack(anchor="w", padx=16, pady=(0, 4))
        self.phase_spectrum = tk.Canvas(
            self.simulation_panel,
            height=190,
            bg="#111821",
            highlightthickness=1,
            highlightbackground="#394657",
        )
        self.phase_spectrum.pack(fill="x", padx=16, pady=(0, 12))
        self.simulation_note = ttk.Label(
            self.simulation_panel, style="Hint.TLabel", justify="left", wraplength=215
        )
        self.simulation_note.pack(anchor="w", padx=16)
        self.magnitude_spectrum.bind("<Configure>", self._redraw_signal_graphs)
        self.phase_spectrum.bind("<Configure>", self._redraw_signal_graphs)

        component_wire_panel = ttk.Frame(self.root, width=230, style="Sidebar.TFrame")
        component_wire_panel.pack(side="right", fill="y")
        component_wire_panel.pack_propagate(False)
        self.components_title = ttk.Label(component_wire_panel, style="Title.TLabel")
        self.components_title.pack(anchor="w", padx=16, pady=(22, 8))
        self.show_component_labels_check = ttk.Checkbutton(
            component_wire_panel,
            style="Sidebar.TCheckbutton",
            variable=self.show_component_labels,
            command=self._toggle_component_labels,
        )
        self.show_component_labels_check.pack(anchor="w", padx=16, pady=(0, 8))
        order_buttons = ttk.Frame(component_wire_panel, style="Sidebar.TFrame")
        order_buttons.pack(fill="x", padx=14, pady=(0, 10))
        self.move_up_button = ttk.Button(
            order_buttons, command=lambda: self._move_selected_components(-1)
        )
        self.move_up_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.move_down_button = ttk.Button(
            order_buttons, command=lambda: self._move_selected_components(1)
        )
        self.move_down_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.component_list = tk.Listbox(
            component_wire_panel,
            selectmode=tk.EXTENDED,
            bg="#18202b",
            fg="#e7edf5",
            selectbackground="#d89720",
            selectforeground="#101820",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            font=("Malgun Gothic", 10),
        )
        self.component_list.pack(fill="both", expand=True, padx=14, pady=(0, 18))
        self.component_list.bind("<<ListboxSelect>>", self._select_from_component_list)

        self.wires_title = ttk.Label(component_wire_panel, style="Title.TLabel")
        self.wires_title.pack(anchor="w", padx=16, pady=(0, 8))
        self.wire_list = tk.Listbox(
            component_wire_panel,
            bg="#18202b",
            fg="#e7edf5",
            selectbackground="#d89720",
            selectforeground="#101820",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none",
            font=("Malgun Gothic", 10),
        )
        self.wire_list.pack(fill="both", expand=True, padx=14, pady=(0, 18))
        self.wire_list.bind("<<ListboxSelect>>", self._select_from_wire_list)

        ttk.Separator(component_wire_panel).pack(fill="x", padx=14)
        self.properties_title = ttk.Label(component_wire_panel, style="Title.TLabel")
        self.properties_title.pack(anchor="w", padx=16, pady=(12, 8))
        properties_scroll_frame = ttk.Frame(component_wire_panel, style="Sidebar.TFrame")
        properties_scroll_frame.pack(fill="x", padx=14, pady=(0, 18))
        self.properties_canvas = tk.Canvas(
            properties_scroll_frame,
            height=190,
            bg="#202936",
            highlightthickness=0,
            borderwidth=0,
        )
        self.properties_scrollbar = ttk.Scrollbar(
            properties_scroll_frame,
            orient="vertical",
            command=self.properties_canvas.yview,
        )
        self.properties_canvas.configure(yscrollcommand=self.properties_scrollbar.set)
        self.properties_scrollbar.pack(side="right", fill="y")
        self.properties_canvas.pack(side="left", fill="both", expand=True)
        self.properties_frame = ttk.Frame(self.properties_canvas, style="Sidebar.TFrame")
        self.properties_window = self.properties_canvas.create_window(
            0, 0, anchor="nw", window=self.properties_frame
        )
        self.properties_frame.bind("<Configure>", self._update_properties_scrollregion)
        self.properties_canvas.bind("<Configure>", self._resize_properties_content)
        self.properties_canvas.bind("<MouseWheel>", self._scroll_properties)
        self.properties_canvas.bind("<Button-4>", lambda event: self._scroll_properties(event, -1))
        self.properties_canvas.bind("<Button-5>", lambda event: self._scroll_properties(event, 1))
        self.property_widgets: dict[str, tuple[tk.StringVar, tk.Widget]] = {}

        canvas_frame = tk.Frame(self.root, bg="#111821", padx=12, pady=12)
        canvas_frame.pack(side="left", fill="both", expand=True)
        self.status_bar = tk.Label(
            canvas_frame, bg="#111821", fg="#cbd5e1", anchor="w",
            padx=4, pady=3, font=("Malgun Gothic", 9),
        )
        self.status_bar.pack(side="bottom", fill="x")
        self.canvas = tk.Canvas(canvas_frame, bg="#f5f7fa", highlightthickness=0, cursor="arrow")
        self.canvas.pack(side="top", fill="both", expand=True)
        self.wire_mode_indicator = self.canvas.create_text(
            0, 0, anchor="se", fill="#2563eb", font=("Malgun Gothic", 13, "bold"),
            state="hidden", tags=("ui_overlay",),
        )
