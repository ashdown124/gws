from __future__ import annotations

import math
import tkinter as tk

from .circuit_simulation import magnitude_and_phase


class SimulationPanelMixin:
    """Signal-simulation scheduling, state refresh, and spectrum rendering."""

    def _apply_cable_capacitance(self, _event: tk.Event | None = None) -> str:
        try:
            value = float(self.cable_capacitance_var.get())
            if not math.isfinite(value) or value < 0.0:
                raise ValueError
        except (ValueError, tk.TclError):
            self.cable_capacitance_var.set(f"{self.cable_capacitance_pf:g}")
            self.root.bell()
            return "break"
        self.cable_capacitance_pf = value
        self.cable_capacitance_var.set(f"{value:g}")
        self.last_electrical_signature = None
        return "break"

    def _change_spectrum_scale(self, _event: tk.Event | None = None) -> None:
        self._update_spectrum_scale_title()
        self._refresh_simulation_panel()

    def _reset_voltage_axis_max(self) -> None:
        magnitudes = list(self.simulation.output_voltage_magnitudes)
        for key, variable in self.pickup_trace_vars.items():
            if variable.get():
                magnitudes.extend(self.simulation.pickup_voltage_magnitudes.get(key, ()))
        self.simulation.voltage_axis_max = max(magnitudes, default=1e-9)
        self._refresh_simulation_panel()

    def _update_spectrum_scale_title(self) -> None:
        if not hasattr(self, "magnitude_spectrum_title"):
            return
        key = (
            "magnitude_spectrum_log_title"
            if self.spectrum_scale_var.get() == "Log"
            else "magnitude_spectrum_title"
        )
        self.magnitude_spectrum_title.configure(text=self.localization.text(key))

    def _run_signal_simulation(self) -> None:
        signature = self._build_electrical_signature()
        if signature != self.last_electrical_signature:
            result = self.circuit_simulator.solve_spectrum(
                self.components,
                self.wires,
                0.0,
                7000.0,
                96,
                cable_capacitance_pf=self.cable_capacitance_pf,
            )
            values = [magnitude_and_phase(output) for output in result.output_voltages]
            self.simulation.frequencies_hz = result.frequencies_hz
            self.simulation.output_voltage_magnitudes = [value[0] for value in values]
            self.simulation.output_phase_degrees = [
                value[1] if value[0] > 1e-12 else 0.0 for value in values
            ]
            self.simulation.pickup_voltage_magnitudes = {
                key: [magnitude_and_phase(output)[0] for output in outputs]
                for key, outputs in result.pickup_output_voltages.items()
            }
            if self.simulation.output_voltage_magnitudes:
                self.simulation.voltage_axis_max = max(
                    self.simulation.voltage_axis_max,
                    max(self.simulation.output_voltage_magnitudes),
                )
            self.simulation.status_key = result.status_key
            self.last_electrical_signature = signature
            self._refresh_simulation_panel()
        self.simulation_job = self.root.after(600, self._run_signal_simulation)

    def _build_electrical_signature(self) -> tuple[object, ...]:
        components = tuple((
            item.component_id, item.kind, tuple(sorted(item.properties.items())),
            item.gauge_value, item.switch_position,
        ) for item in self.components.values())
        wires = tuple((
            wire.wire_id, wire.start_endpoint_canvas_id, wire.end_endpoint_canvas_id,
            tuple(wire.node_canvas_ids)
        ) for wire in self.wires)
        return components, wires, self.cable_capacitance_pf

    def _refresh_simulation_panel(self) -> None:
        if self.simulation.status_key == "simulation_running":
            self._draw_signal_spectra()
        else:
            self._draw_signal_placeholder()

    @staticmethod
    def _spectrum_x(
        frequency: float, left: float, right: float
    ) -> float:
        ratio = max(0.0, min(1.0, frequency / 7000.0))
        return left + ratio * (right - left)

    def _draw_spectrum_axes(self, canvas: tk.Canvas, phase: bool) -> tuple[float, float, float, float]:
        canvas.delete("all")
        width, height = max(160, canvas.winfo_width()), max(120, canvas.winfo_height())
        left, right, top, bottom = 42.0, width - 8.0, 10.0, height - 25.0
        for frequency in (0, 1000, 3000, 5000, 7000):
            x = self._spectrum_x(frequency, left, right)
            canvas.create_line(x, top, x, bottom, fill="#1f2b39")
            label = f"{frequency // 1000}k" if frequency >= 1000 else "0"
            canvas.create_text(x, bottom + 12, text=label, fill="#94a3b8", font=("Arial", 8))
        for fraction in (0.0, 0.5, 1.0):
            y = top + fraction * (bottom - top)
            canvas.create_line(left, y, right, y, fill="#1f2b39")
        canvas.create_line(left, top, left, bottom, fill="#64748b")
        canvas.create_line(left, bottom, right, bottom, fill="#64748b")
        if phase:
            for value, fraction in ((180, 0.0), (0, 0.5), (-180, 1.0)):
                canvas.create_text(left - 5, top + fraction * (bottom - top), text=str(value),
                                   anchor="e", fill="#94a3b8", font=("Arial", 8))
        return left, right, top, bottom

    def _draw_signal_spectra(self) -> None:
        frequencies = self.simulation.frequencies_hz
        magnitudes = self.simulation.output_voltage_magnitudes
        if not frequencies or not magnitudes:
            self._draw_signal_placeholder()
            return
        left, right, top, bottom = self._draw_spectrum_axes(self.magnitude_spectrum, False)
        enabled = [key for key, variable in self.pickup_trace_vars.items()
                   if variable.get() and key in self.simulation.pickup_voltage_magnitudes]
        maximum = max(self.simulation.voltage_axis_max, max(magnitudes), 1e-9)
        for key in enabled:
            maximum = max(
                maximum,
                max(self.simulation.pickup_voltage_magnitudes[key], default=0.0),
            )
        self.simulation.voltage_axis_max = maximum
        log_scale = self.spectrum_scale_var.get() == "Log"
        log_bounds: tuple[float, float] | None = None
        if log_scale:
            maximum_db = 20.0 * math.log10(maximum)
            top_db = max(0.0, math.ceil(maximum_db / 10.0) * 10.0)
            bottom_db = top_db - 80.0
            log_bounds = (bottom_db, top_db)
            for value, y in (
                (top_db, top),
                ((top_db + bottom_db) / 2.0, (top + bottom) / 2.0),
                (bottom_db, bottom),
            ):
                self.magnitude_spectrum.create_text(
                    left - 5, y, text=f"{value:.0f}", anchor="e",
                    fill="#94a3b8", font=("Arial", 8),
                )
        else:
            self.magnitude_spectrum.create_text(
                left - 5, top, text=f"{maximum:.3g}", anchor="e",
                fill="#94a3b8", font=("Arial", 8),
            )
            self.magnitude_spectrum.create_text(
                left - 5, bottom, text="0", anchor="e",
                fill="#94a3b8", font=("Arial", 8),
            )
        self._draw_magnitude_trace(
            frequencies, magnitudes, maximum, left, right, top, bottom,
            "#22c55e", log_bounds=log_bounds,
        )
        for key in enabled:
            self._draw_magnitude_trace(
                frequencies, self.simulation.pickup_voltage_magnitudes[key], maximum,
                left, right, top, bottom, self._pickup_trace_color(key), (5, 3),
                log_bounds,
            )
        left, right, top, bottom = self._draw_spectrum_axes(self.phase_spectrum, True)
        points: list[float] = []
        for frequency, phase in zip(frequencies, self.simulation.output_phase_degrees):
            x = self._spectrum_x(frequency, left, right)
            y = top + (180.0 - max(-180.0, min(180.0, phase))) / 360.0 * (bottom - top)
            points.extend((x, y))
        if len(points) >= 4:
            self.phase_spectrum.create_line(*points, fill="#38bdf8", width=2, smooth=True)

    def _draw_magnitude_trace(self, frequencies, magnitudes, maximum, left, right, top, bottom,
                              color: str, dash=None, log_bounds=None) -> None:
        points: list[float] = []
        for frequency, magnitude in zip(frequencies, magnitudes):
            x = self._spectrum_x(frequency, left, right)
            if log_bounds is None:
                ratio = magnitude / maximum
            else:
                lower_db, upper_db = log_bounds
                magnitude_db = 20.0 * math.log10(max(magnitude, 1e-12))
                magnitude_db = max(lower_db, min(upper_db, magnitude_db))
                ratio = (magnitude_db - lower_db) / (upper_db - lower_db)
            points.extend((x, bottom - ratio * (bottom - top)))
        if len(points) >= 4:
            self.magnitude_spectrum.create_line(
                *points, fill=color, width=2, dash=dash, smooth=True
            )

    def _draw_signal_placeholder(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "magnitude_spectrum"):
            return
        visible_statuses = {"simulation_no_jack", "simulation_open_output"}
        message_key = (
            self.simulation.status_key
            if self.simulation.status_key in visible_statuses else "waveform_pending"
        )
        for canvas, phase in ((self.magnitude_spectrum, False), (self.phase_spectrum, True)):
            left, right, top, bottom = self._draw_spectrum_axes(canvas, phase)
            canvas.create_line(left, (top + bottom) / 2, right, (top + bottom) / 2,
                               fill="#64748b", width=2)
            canvas.create_text((left + right) / 2, top + 18,
                               text=self.localization.text(message_key),
                               fill="#94a3b8", font=("Malgun Gothic", 9))

    def _redraw_signal_graphs(self, _event: tk.Event | None = None) -> None:
        if self.simulation.status_key == "simulation_running":
            self._draw_signal_spectra()
        else:
            self._draw_signal_placeholder()
