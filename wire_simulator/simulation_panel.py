from __future__ import annotations

import math
import tkinter as tk

from .circuit_simulation import magnitude_and_phase


class SimulationPanelMixin:
    """Signal-simulation scheduling, state refresh, and spectrum rendering."""

    def _run_signal_simulation(self) -> None:
        signature = self._electrical_signature()
        if signature != self.simulation_signature:
            result = self.circuit_simulator.solve_spectrum(
                self.components, self.wires, 50.0, 5000.0, 96
            )
            values = [magnitude_and_phase(output) for output in result.outputs]
            self.simulation.frequencies = result.frequencies
            self.simulation.magnitudes = [value[0] for value in values]
            self.simulation.phases = [value[1] if value[0] > 1e-12 else 0.0 for value in values]
            self.simulation.pickup_magnitudes = {
                key: [magnitude_and_phase(output)[0] for output in outputs]
                for key, outputs in result.pickup_outputs.items()
            }
            if self.simulation.magnitudes:
                self.simulation.magnitude_axis_max = max(
                    self.simulation.magnitude_axis_max, max(self.simulation.magnitudes)
                )
            self.simulation.status_key = result.status_key
            self.simulation_signature = signature
            self._refresh_simulation_panel()
        self.simulation_job = self.root.after(600, self._run_signal_simulation)

    def _electrical_signature(self) -> tuple[object, ...]:
        components = tuple((
            item.component_id, item.kind, tuple(sorted(item.properties.items())),
            item.gauge_value, item.switch_position,
        ) for item in self.components.values())
        wires = tuple((
            wire.wire_id, wire.start_endpoint, wire.end_endpoint, tuple(wire.node_items)
        ) for wire in self.wires)
        return components, wires

    def _refresh_simulation_panel(self) -> None:
        if self.simulation.status_key == "simulation_running":
            self._draw_signal_spectra()
        else:
            self._draw_signal_placeholder()

    def _draw_spectrum_axes(self, canvas: tk.Canvas, phase: bool) -> tuple[float, float, float, float]:
        canvas.delete("all")
        width, height = max(160, canvas.winfo_width()), max(120, canvas.winfo_height())
        left, right, top, bottom = 42.0, width - 8.0, 10.0, height - 25.0
        for frequency in (50, 100, 500, 1000, 5000):
            x = left + math.log10(frequency / 50.0) / 2.0 * (right - left)
            canvas.create_line(x, top, x, bottom, fill="#1f2b39")
            label = f"{frequency // 1000}k" if frequency >= 1000 else str(frequency)
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
        frequencies = self.simulation.frequencies
        magnitudes = self.simulation.magnitudes
        if not frequencies or not magnitudes:
            self._draw_signal_placeholder()
            return
        left, right, top, bottom = self._draw_spectrum_axes(self.magnitude_spectrum, False)
        enabled = [key for key, variable in self.pickup_trace_vars.items()
                   if variable.get() and key in self.simulation.pickup_magnitudes]
        maximum = max(self.simulation.magnitude_axis_max, max(magnitudes), 1e-9)
        for key in enabled:
            maximum = max(maximum, max(self.simulation.pickup_magnitudes[key], default=0.0))
        self.simulation.magnitude_axis_max = maximum
        self.magnitude_spectrum.create_text(left - 5, top, text=f"{maximum:.3g}", anchor="e",
                                            fill="#94a3b8", font=("Arial", 8))
        self.magnitude_spectrum.create_text(left - 5, bottom, text="0", anchor="e",
                                            fill="#94a3b8", font=("Arial", 8))
        self._draw_magnitude_trace(frequencies, magnitudes, maximum, left, right, top, bottom,
                                   "#22c55e")
        for key in enabled:
            self._draw_magnitude_trace(
                frequencies, self.simulation.pickup_magnitudes[key], maximum,
                left, right, top, bottom, self._pickup_trace_color(key), (5, 3),
            )
        left, right, top, bottom = self._draw_spectrum_axes(self.phase_spectrum, True)
        points: list[float] = []
        for frequency, phase in zip(frequencies, self.simulation.phases):
            x = left + math.log10(frequency / 50.0) / 2.0 * (right - left)
            y = top + (180.0 - max(-180.0, min(180.0, phase))) / 360.0 * (bottom - top)
            points.extend((x, y))
        if len(points) >= 4:
            self.phase_spectrum.create_line(*points, fill="#38bdf8", width=2, smooth=True)

    def _draw_magnitude_trace(self, frequencies, magnitudes, maximum, left, right, top, bottom,
                              color: str, dash=None) -> None:
        points: list[float] = []
        for frequency, magnitude in zip(frequencies, magnitudes):
            x = left + math.log10(frequency / 50.0) / 2.0 * (right - left)
            points.extend((x, bottom - magnitude / maximum * (bottom - top)))
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
