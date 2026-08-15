from __future__ import annotations

from dataclasses import dataclass, field
import cmath
import math
from typing import Any


@dataclass
class SignalSimulationState:
    jack_hot_output: float = 0.0
    complex_output: complex = 0j
    status_key: str = "simulation_inactive"
    frequencies: list[float] = field(default_factory=list)
    magnitudes: list[float] = field(default_factory=list)
    phases: list[float] = field(default_factory=list)
    magnitude_axis_max: float = 0.0
    pickup_magnitudes: dict[str, list[float]] = field(default_factory=dict)

    def reset_output(self) -> None:
        self.jack_hot_output = 0.0
        self.complex_output = 0j
        self.frequencies = []
        self.magnitudes = []
        self.phases = []
        self.magnitude_axis_max = 0.0
        self.pickup_magnitudes = {}


@dataclass(frozen=True)
class SimulationResult:
    output: complex
    status_key: str


@dataclass(frozen=True)
class SpectrumResult:
    frequencies: list[float]
    outputs: list[complex]
    status_key: str
    pickup_outputs: dict[str, list[complex]] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledResponse:
    """Frequency-independent circuit topology and element parameters."""

    size: int
    hot_index: int
    ground_index: int
    resistors: list[tuple[int, int, float]]
    capacitors: list[tuple[int, int, float]]
    pickups: list[tuple[str, int, int, float, float, float]]
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
        components: dict[str, Any],
        wires: list[Any],
        start_hz: float = 50.0,
        end_hz: float = 5000.0,
        point_count: int = 96,
    ) -> SpectrumResult:
        frequencies = [
            start_hz * (end_hz / start_hz) ** (index / (point_count - 1))
            for index in range(point_count)
        ]
        response = self.compile_response(components, wires)
        if response.status_key != "simulation_running":
            return SpectrumResult(
                frequencies, [0j for _ in frequencies], response.status_key
            )
        outputs: list[complex] = []
        status_key = "simulation_running"
        for frequency in frequencies:
            result = self.evaluate_response(response, frequency)
            if result.status_key != "simulation_running":
                status_key = result.status_key
                outputs = [0j for _ in frequencies]
                break
            outputs.append(result.output)
        pickup_outputs: dict[str, list[complex]] = {}
        if status_key == "simulation_running":
            source_keys = sorted({pickup[0] for pickup in response.pickups})
            for source_key in source_keys:
                pickup_outputs[source_key] = [
                    self.evaluate_response(response, frequency, source_key).output
                    for frequency in frequencies
                ]
        return SpectrumResult(frequencies, outputs, status_key, pickup_outputs)

    def compile_response(
        self, components: dict[str, Any], wires: list[Any]
    ) -> CompiledResponse:
        union = _UnionFind()
        for component in components.values():
            for terminal in component.electrical_terminals().values():
                union.add(terminal)
        for wire in wires:
            endpoints = [wire.start_endpoint, *wire.node_items, wire.end_endpoint]
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
        resistors: list[tuple[int, int, float]] = []
        capacitors: list[tuple[int, int, float]] = []
        pickups: list[tuple[str, int, int, float, float, float]] = []

        def endpoints(first: int, second: int) -> tuple[int, int]:
            first_root, second_root = union.find(first), union.find(second)
            adjacency[first_root].add(second_root)
            adjacency[second_root].add(first_root)
            return indices[first_root], indices[second_root]

        for component in components.values():
            terminals = component.electrical_terminals()
            if component.kind == "pickup":
                resistance = self._scaled_value(
                    component.properties["resistance"],
                    component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                inductance = self._scaled_value(
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
                        pickups.append((source_key, first, second, source_voltage,
                                        resistance / 2, inductance / 2))
                else:
                    first, second = endpoints(terminals["hot"], terminals["gnd"])
                    pickups.append((str(component.component_id), first, second, source_voltage,
                                    resistance, inductance))
            elif component.kind == "resistor":
                resistance = self._scaled_value(
                    component.properties["resistance"], component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                first, second = endpoints(terminals["1"], terminals["2"])
                resistors.append((first, second, 1 / resistance))
            elif component.kind == "capacitor":
                capacitance = self._scaled_value(
                    component.properties["capacitance"], component.properties["capacitance_unit"],
                    {"pF": 1e-12, "nF": 1e-9, "µF": 1e-6},
                )
                first, second = endpoints(terminals["1"], terminals["2"])
                capacitors.append((first, second, capacitance))
            elif component.kind == "potentiometer":
                resistance = self._scaled_value(
                    component.properties["resistance"], component.properties["resistance_unit"],
                    {"kΩ": 1e3, "MΩ": 1e6},
                )
                resistance_12, resistance_23 = self.potentiometer_segment_resistances(
                    resistance, component.gauge_value, component.properties["taper"]
                )
                if resistance_12 > 0.0:
                    first, second = endpoints(terminals["1"], terminals["2"])
                    resistors.append((first, second, 1 / resistance_12))
                if resistance_23 > 0.0:
                    first, second = endpoints(terminals["2"], terminals["3"])
                    resistors.append((first, second, 1 / resistance_23))

        status = "simulation_running"
        if not self._reachable(hot_root, ground_root, adjacency):
            status = "simulation_open_output"
        return CompiledResponse(
            len(indices), indices[hot_root], indices[ground_root],
            resistors, capacitors, pickups, status,
        )

    def evaluate_response(
        self, response: CompiledResponse, frequency_hz: float,
        active_source_key: str | None = None,
    ) -> SimulationResult:
        if response.status_key != "simulation_running":
            return SimulationResult(0j, response.status_key)
        omega = 2 * math.pi * max(1.0, float(frequency_hz))
        matrix = [[0j for _ in range(response.size)] for _ in range(response.size)]
        currents = [0j for _ in range(response.size)]

        def stamp(first: int, second: int, admittance: complex) -> None:
            matrix[first][first] += admittance
            matrix[second][second] += admittance
            matrix[first][second] -= admittance
            matrix[second][first] -= admittance

        for first, second, conductance in response.resistors:
            stamp(first, second, conductance)
        for first, second, capacitance in response.capacitors:
            stamp(first, second, 1j * omega * capacitance)
        for source_key, hot, ground, source_voltage, resistance, inductance in response.pickups:
            admittance = 1 / complex(resistance, omega * inductance)
            stamp(hot, ground, admittance)
            if active_source_key is None or source_key == active_source_key:
                source_current = source_voltage * admittance
                currents[hot] += source_current
                currents[ground] -= source_current
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
        components: dict[str, Any],
        wires: list[Any],
        frequency_hz: float,
    ) -> SimulationResult:
        frequency_hz = max(1.0, float(frequency_hz))
        omega = 2 * math.pi * frequency_hz
        union = _UnionFind()

        for component in components.values():
            for terminal in component.electrical_terminals().values():
                union.add(terminal)
        for wire in wires:
            endpoints = [wire.start_endpoint, *wire.node_items, wire.end_endpoint]
            for endpoint in endpoints:
                union.add(endpoint)
            for endpoint in endpoints[1:]:
                union.union(endpoints[0], endpoint)

        ground_items = [
            component.electrical_terminals()["gnd"]
            for component in components.values()
            if component.kind == "ground"
        ]
        for ground in ground_items[1:]:
            union.union(ground_items[0], ground)

        for component in components.values():
            if component.kind != "switch":
                if component.kind == "potentiometer":
                    terminals = component.electrical_terminals()
                    ratio = self.potentiometer_taper_ratio(
                        component.gauge_value, component.properties["taper"]
                    )
                    if ratio <= 0.0:
                        union.union(terminals["1"], terminals["2"])
                    elif ratio >= 1.0:
                        union.union(terminals["2"], terminals["3"])
                continue
            terminals = component.electrical_terminals()
            for group in component.active_switch_groups().values():
                group_items = [terminals[name] for name in group]
                for item in group_items[1:]:
                    union.union(group_items[0], item)

        jacks = [component for component in components.values() if component.kind == "jack"]
        if not jacks:
            return SimulationResult(0j, "simulation_no_jack")
        jack = jacks[0]
        jack_terminals = jack.electrical_terminals()
        hot_root = union.find(jack_terminals["hot"])
        ground_root = union.find(jack_terminals["gnd"])

        roots = {union.find(item) for item in union.parent}
        root_list = sorted(roots)
        indices = {root: index for index, root in enumerate(root_list)}
        size = len(root_list)
        matrix = [[0j for _ in range(size)] for _ in range(size)]
        currents = [0j for _ in range(size)]
        adjacency: dict[int, set[int]] = {root: set() for root in roots}

        def connect(first_item: int, second_item: int) -> tuple[int, int]:
            first, second = union.find(first_item), union.find(second_item)
            adjacency[first].add(second)
            adjacency[second].add(first)
            return indices[first], indices[second]

        def stamp_admittance(first_item: int, second_item: int, admittance: complex) -> None:
            first, second = connect(first_item, second_item)
            matrix[first][first] += admittance
            matrix[second][second] += admittance
            matrix[first][second] -= admittance
            matrix[second][first] -= admittance

        def stamp_norton(
            hot_item: int, gnd_item: int, source_voltage: complex, impedance: complex
        ) -> None:
            admittance = 1 / impedance
            stamp_admittance(hot_item, gnd_item, admittance)
            hot_index = indices[union.find(hot_item)]
            gnd_index = indices[union.find(gnd_item)]
            source_current = source_voltage / impedance
            currents[hot_index] += source_current
            currents[gnd_index] -= source_current

        for component in components.values():
            terminals = component.electrical_terminals()
            if component.kind == "pickup":
                source_phase = 0.0
                resistance = self._scaled_value(
                    component.properties["resistance"],
                    component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                inductance = self._scaled_value(
                    component.properties["inductance"],
                    component.properties["inductance_unit"],
                    {"mH": 1e-3, "H": 1.0},
                )
                source_voltage = max(
                    0.0, float(component.properties["output_sensitivity"])
                ) / 100.0
                if component.properties["pickup_type"] == "humbucker":
                    coil_resistance = resistance / 2
                    coil_inductance = inductance / 2
                    for coil in ("north", "south"):
                        stamp_norton(
                            terminals[f"{coil}_hot"], terminals[f"{coil}_gnd"],
                            cmath.rect(source_voltage, source_phase),
                            complex(coil_resistance, omega * coil_inductance),
                        )
                else:
                    stamp_norton(
                        terminals["hot"], terminals["gnd"],
                        cmath.rect(source_voltage, source_phase),
                        complex(resistance, omega * inductance),
                    )
            elif component.kind == "resistor":
                resistance = self._scaled_value(
                    component.properties["resistance"],
                    component.properties["resistance_unit"],
                    {"Ω": 1.0, "kΩ": 1e3, "MΩ": 1e6},
                )
                stamp_admittance(terminals["1"], terminals["2"], 1 / resistance)
            elif component.kind == "capacitor":
                capacitance = self._scaled_value(
                    component.properties["capacitance"],
                    component.properties["capacitance_unit"],
                    {"pF": 1e-12, "nF": 1e-9, "µF": 1e-6},
                )
                stamp_admittance(terminals["1"], terminals["2"], 1j * omega * capacitance)
            elif component.kind == "potentiometer":
                resistance = self._scaled_value(
                    component.properties["resistance"],
                    component.properties["resistance_unit"],
                    {"kΩ": 1e3, "MΩ": 1e6},
                )
                resistance_12, resistance_23 = self.potentiometer_segment_resistances(
                    resistance, component.gauge_value, component.properties["taper"]
                )
                if resistance_12 > 0.0:
                    stamp_admittance(
                        terminals["1"], terminals["2"], 1 / resistance_12
                    )
                if resistance_23 > 0.0:
                    stamp_admittance(
                        terminals["2"], terminals["3"], 1 / resistance_23
                    )

        if not self._reachable(hot_root, ground_root, adjacency):
            return SimulationResult(0j, "simulation_open_output")

        for index in range(size):
            matrix[index][index] += 1e-12
        reference = indices[ground_root]
        for index in range(size):
            matrix[reference][index] = 0j
            matrix[index][reference] = 0j
        matrix[reference][reference] = 1 + 0j
        currents[reference] = 0j

        try:
            voltages = self._solve_linear_system(matrix, currents)
        except ValueError:
            return SimulationResult(0j, "simulation_solver_error")
        output = voltages[indices[hot_root]] - voltages[indices[ground_root]]
        return SimulationResult(output, "simulation_running")

    @staticmethod
    def _scaled_value(value: str, unit: str, scales: dict[str, float]) -> float:
        return max(float(value) * scales[unit], 1e-18)

    @staticmethod
    def _reachable(start: int, target: int, adjacency: dict[int, set[int]]) -> bool:
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
