from __future__ import annotations

import cmath
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Protocol


PICKUP_COIL_CAPACITANCE_F = 100e-12
JACK_OUTPUT_LOAD_OHMS = 1e6


class CircuitComponent(Protocol):
    component_id: int
    kind: str
    properties: dict[str, str]
    gauge_value: int
    switch_position: int

    def electrical_terminals(self) -> dict[str, int]: ...

    def active_switch_groups(self) -> dict[str, set[str]]: ...


class CircuitWire(Protocol):
    start_endpoint_canvas_id: int
    end_endpoint_canvas_id: int
    node_canvas_ids: list[int]


@dataclass
class SignalSimulationState:
    status_key: str = "simulation_inactive"
    frequencies_hz: list[float] = field(default_factory=list)
    output_voltage_magnitudes: list[float] = field(default_factory=list)
    output_phase_degrees: list[float] = field(default_factory=list)
    voltage_axis_max: float = 0.0
    pickup_voltage_magnitudes: dict[str, list[float]] = field(default_factory=dict)

    def reset_results(self) -> None:
        self.frequencies_hz = []
        self.output_voltage_magnitudes = []
        self.output_phase_degrees = []
        self.voltage_axis_max = 0.0
        self.pickup_voltage_magnitudes = {}


@dataclass(frozen=True)
class SimulationResult:
    output_voltage: complex
    status_key: str


@dataclass(frozen=True)
class SpectrumResult:
    frequencies_hz: list[float]
    output_voltages: list[complex]
    status_key: str
    pickup_output_voltages: dict[str, list[complex]] = field(default_factory=dict)


@dataclass(frozen=True)
class ConductanceBranch:
    first_node: int
    second_node: int
    conductance_siemens: float


@dataclass(frozen=True)
class CapacitanceBranch:
    first_node: int
    second_node: int
    capacitance_f: float


@dataclass(frozen=True)
class PickupSource:
    source_key: str
    hot_node: int
    ground_node: int
    source_voltage: float
    resistance_ohms: float
    inductance_h: float


@dataclass(frozen=True)
class CompiledResponse:
    """Frequency-independent circuit topology and element parameters."""

    size: int
    hot_index: int
    ground_index: int
    conductance_branches: list[ConductanceBranch]
    capacitance_branches: list[CapacitanceBranch]
    pickup_sources: list[PickupSource]
    status_key: str = "simulation_running"


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def add(self, item: int) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: int) -> int:
        self.add(item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        first_root, second_root = self.find(first), self.find(second)
        if first_root != second_root:
            self.parent[second_root] = first_root


class CircuitSimulator:
    """Small-signal sinusoidal solver using complex nodal analysis."""

    @staticmethod
    def potentiometer_taper_ratio(
        gauge_value: float, taper: str = "audio_taper"
    ) -> float:
        """Convert mechanical travel into the selected electrical taper ratio."""
        linear_position = max(0.0, min(100.0, float(gauge_value))) / 100.0
        exponent = 3.321928094887362
        if taper == "linear_taper":
            return linear_position
        if taper == "reverse_audio_taper":
            return 1.0 - (1.0 - linear_position) ** exponent
        return linear_position ** exponent

    @classmethod
    def potentiometer_segment_resistances(
        cls, resistance: float, gauge_value: float, taper: str
    ) -> tuple[float, float]:
        """Return the physical track resistances R(1-2) and R(2-3)."""
        ratio = cls.potentiometer_taper_ratio(gauge_value, taper)
        total = max(0.0, float(resistance))
        return total * ratio, total * (1.0 - ratio)

    def solve_spectrum(
        self,
        components: Mapping[str, CircuitComponent],
        wires: Sequence[CircuitWire],
        start_hz: float = 0.0,
        end_hz: float = 7000.0,
        point_count: int = 96,
        cable_capacitance_pf: float = 300.0,
    ) -> SpectrumResult:
        if point_count <= 1:
            frequencies_hz = [start_hz]
        elif start_hz <= 0.0:
            frequencies_hz = [
                start_hz + (end_hz - start_hz) * index / (point_count - 1)
                for index in range(point_count)
            ]
        else:
            frequencies_hz = [
                start_hz * (end_hz / start_hz) ** (index / (point_count - 1))
                for index in range(point_count)
            ]
        response = self.compile_response(
            components, wires, cable_capacitance_pf=cable_capacitance_pf
        )
        if response.status_key != "simulation_running":
            return SpectrumResult(
                frequencies_hz,
                [0j for _ in frequencies_hz],
                response.status_key,
            )
        output_voltages: list[complex] = []
        status_key = "simulation_running"
        for frequency_hz in frequencies_hz:
            result = self.evaluate_response(response, frequency_hz)
            if result.status_key != "simulation_running":
                status_key = result.status_key
                output_voltages = [0j for _ in frequencies_hz]
                break
            output_voltages.append(result.output_voltage)
        pickup_output_voltages: dict[str, list[complex]] = {}
        if status_key == "simulation_running":
            source_keys = sorted(
                {source.source_key for source in response.pickup_sources}
            )
            for source_key in source_keys:
                pickup_output_voltages[source_key] = [
                    self.evaluate_response(
                        response, frequency_hz, source_key
                    ).output_voltage
                    for frequency_hz in frequencies_hz
                ]
        return SpectrumResult(
            frequencies_hz, output_voltages, status_key, pickup_output_voltages
        )

    def compile_response(
        self,
        components: Mapping[str, CircuitComponent],
        wires: Sequence[CircuitWire],
        cable_capacitance_pf: float = 300.0,
    ) -> CompiledResponse:
        union = _UnionFind()
        for component in components.values():
            for terminal in component.electrical_terminals().values():
                union.add(terminal)
        for wire in wires:
            endpoints = [
                wire.start_endpoint_canvas_id,
                *wire.node_canvas_ids,
                wire.end_endpoint_canvas_id,
            ]
            for endpoint in endpoints:
                union.add(endpoint)
            for endpoint in endpoints[1:]:
                union.union(endpoints[0], endpoint)
        ground_items = [
            component.electrical_terminals()["gnd"]
            for component in components.values() if component.kind == "ground"
        ]
        for ground in ground_items[1:]:
            union.union(ground_items[0], ground)
        for component in components.values():
            if component.kind == "switch":
                terminals = component.electrical_terminals()
                for group in component.active_switch_groups().values():
                    items = [terminals[name] for name in group]
                    for item in items[1:]:
                        union.union(items[0], item)
            elif component.kind == "potentiometer":
                terminals = component.electrical_terminals()
                ratio = self.potentiometer_taper_ratio(
                    component.gauge_value, component.properties["taper"]
                )
                if ratio <= 0.0:
                    union.union(terminals["1"], terminals["2"])
                elif ratio >= 1.0:
                    union.union(terminals["2"], terminals["3"])

        jacks = [component for component in components.values() if component.kind == "jack"]
        if not jacks:
            return CompiledResponse(0, 0, 0, [], [], [], "simulation_no_jack")
        jack_terminals = jacks[0].electrical_terminals()
        hot_root = union.find(jack_terminals["hot"])
        ground_root = union.find(jack_terminals["gnd"])
        roots = {union.find(item) for item in union.parent}
        indices = {root: index for index, root in enumerate(sorted(roots))}
        adjacency: dict[int, set[int]] = {root: set() for root in roots}
        conductance_branches: list[ConductanceBranch] = []
        capacitance_branches: list[CapacitanceBranch] = []
        pickup_sources: list[PickupSource] = []

        def endpoints(first: int, second: int) -> tuple[int, int]:
            first_root, second_root = union.find(first), union.find(second)
            adjacency[first_root].add(second_root)
            adjacency[second_root].add(first_root)
            return indices[first_root], indices[second_root]

        for component in components.values():
            terminals = component.electrical_terminals()
            if component.kind == "pickup":
                resistance = self._convert_to_base_units(
                    component.properties["resistance"],
                    component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                inductance = self._convert_to_base_units(
                    component.properties["inductance"],
                    component.properties["inductance_unit"],
                    {"mH": 1e-3, "H": 1.0},
                )
                source_voltage = max(
                    0.0, float(component.properties["output_sensitivity"])
                ) / 100.0
                if component.properties["pickup_type"] == "humbucker":
                    for coil in ("north", "south"):
                        first, second = endpoints(
                            terminals[f"{coil}_hot"], terminals[f"{coil}_gnd"]
                        )
                        source_key = f"{component.component_id}:{coil[0].upper()}"
                        pickup_sources.append(PickupSource(
                            source_key, first, second, source_voltage,
                            resistance / 2, inductance / 2,
                        ))
                        capacitance_branches.append(CapacitanceBranch(
                            first, second, PICKUP_COIL_CAPACITANCE_F
                        ))
                else:
                    first, second = endpoints(terminals["hot"], terminals["gnd"])
                    pickup_sources.append(PickupSource(
                        str(component.component_id), first, second,
                        source_voltage, resistance, inductance,
                    ))
                    capacitance_branches.append(CapacitanceBranch(
                        first, second, PICKUP_COIL_CAPACITANCE_F
                    ))
            elif component.kind == "resistor":
                resistance = self._convert_to_base_units(
                    component.properties["resistance"], component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                first, second = endpoints(terminals["1"], terminals["2"])
                conductance_branches.append(ConductanceBranch(
                    first, second, 1 / resistance
                ))
            elif component.kind == "capacitor":
                capacitance = self._convert_to_base_units(
                    component.properties["capacitance"], component.properties["capacitance_unit"],
                    {"pF": 1e-12, "nF": 1e-9, "µF": 1e-6},
                )
                first, second = endpoints(terminals["1"], terminals["2"])
                capacitance_branches.append(CapacitanceBranch(
                    first, second, capacitance
                ))
            elif component.kind == "potentiometer":
                resistance = self._convert_to_base_units(
                    component.properties["resistance"], component.properties["resistance_unit"],
                    {"kΩ": 1e3, "MΩ": 1e6},
                )
                resistance_12, resistance_23 = self.potentiometer_segment_resistances(
                    resistance, component.gauge_value, component.properties["taper"]
                )
                if resistance_12 > 0.0:
                    first, second = endpoints(terminals["1"], terminals["2"])
                    conductance_branches.append(ConductanceBranch(
                        first, second, 1 / resistance_12
                    ))
                if resistance_23 > 0.0:
                    first, second = endpoints(terminals["2"], terminals["3"])
                    conductance_branches.append(ConductanceBranch(
                        first, second, 1 / resistance_23
                    ))

        status = "simulation_running"
        if not self._has_signal_path(hot_root, ground_root, adjacency):
            status = "simulation_open_output"
        cable_capacitance = max(0.0, float(cable_capacitance_pf)) * 1e-12
        if cable_capacitance > 0.0:
            capacitance_branches.append(CapacitanceBranch(
                indices[hot_root], indices[ground_root], cable_capacitance
            ))
        conductance_branches.append(ConductanceBranch(
            indices[hot_root], indices[ground_root], 1 / JACK_OUTPUT_LOAD_OHMS
        ))
        return CompiledResponse(
            len(indices), indices[hot_root], indices[ground_root],
            conductance_branches, capacitance_branches, pickup_sources, status,
        )

    def evaluate_response(
        self, response: CompiledResponse, frequency_hz: float,
        excited_source_key: str | None = None,
    ) -> SimulationResult:
        if response.status_key != "simulation_running":
            return SimulationResult(0j, response.status_key)
        omega = 2 * math.pi * max(0.0, float(frequency_hz))
        matrix = [[0j for _ in range(response.size)] for _ in range(response.size)]
        currents = [0j for _ in range(response.size)]

        def stamp(first: int, second: int, admittance: complex) -> None:
            matrix[first][first] += admittance
            matrix[second][second] += admittance
            matrix[first][second] -= admittance
            matrix[second][first] -= admittance

        for branch in response.conductance_branches:
            stamp(
                branch.first_node,
                branch.second_node,
                branch.conductance_siemens,
            )
        for branch in response.capacitance_branches:
            stamp(
                branch.first_node,
                branch.second_node,
                1j * omega * branch.capacitance_f,
            )
        for source in response.pickup_sources:
            admittance = 1 / complex(
                source.resistance_ohms, omega * source.inductance_h
            )
            stamp(source.hot_node, source.ground_node, admittance)
            if excited_source_key is None or source.source_key == excited_source_key:
                source_current = source.source_voltage * admittance
                currents[source.hot_node] += source_current
                currents[source.ground_node] -= source_current
        for index in range(response.size):
            matrix[index][index] += 1e-12
        reference = response.ground_index
        for index in range(response.size):
            matrix[reference][index] = 0j
            matrix[index][reference] = 0j
        matrix[reference][reference] = 1 + 0j
        currents[reference] = 0j
        try:
            voltages = self._solve_linear_system(matrix, currents)
        except ValueError:
            return SimulationResult(0j, "simulation_solver_error")
        return SimulationResult(
            voltages[response.hot_index] - voltages[response.ground_index],
            "simulation_running",
        )

    def solve(
        self,
        components: Mapping[str, CircuitComponent],
        wires: Sequence[CircuitWire],
        frequency_hz: float,
        cable_capacitance_pf: float = 300.0,
    ) -> SimulationResult:
        """Evaluate one frequency through the shared compiled-response path."""
        response = self.compile_response(
            components, wires, cable_capacitance_pf=cable_capacitance_pf
        )
        return self.evaluate_response(response, frequency_hz)

    @staticmethod
    def _convert_to_base_units(value: str, unit: str, scales: dict[str, float]) -> float:
        return max(float(value) * scales[unit], 1e-18)

    @staticmethod
    def _has_signal_path(start: int, target: int, adjacency: dict[int, set[int]]) -> bool:
        pending, visited = [start], set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(adjacency.get(current, set()) - visited)
        return False

    @staticmethod
    def _solve_linear_system(matrix: list[list[complex]], values: list[complex]) -> list[complex]:
        size = len(values)
        augmented = [row[:] + [values[index]] for index, row in enumerate(matrix)]
        for column in range(size):
            pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-18:
                raise ValueError("singular circuit matrix")
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            augmented[column] = [value / divisor for value in augmented[column]]
            for row in range(size):
                if row == column:
                    continue
                factor = augmented[row][column]
                if factor:
                    augmented[row] = [
                        current - factor * pivot_value
                        for current, pivot_value in zip(augmented[row], augmented[column])
                    ]
        return [augmented[index][-1] for index in range(size)]


def magnitude_and_phase(signal: complex) -> tuple[float, float]:
    magnitude = abs(signal)
    phase = math.degrees(cmath.phase(signal)) if magnitude > 1e-12 else 0.0
    return magnitude, phase
