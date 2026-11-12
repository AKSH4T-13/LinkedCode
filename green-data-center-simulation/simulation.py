"""Illustrative, deterministic seminar model. No measured facility data."""
from dataclasses import dataclass, field
from math import exp

STEP_SECONDS = 10


def power(workload: float, liquid: bool = False) -> dict:
    if not 0 <= workload <= 100:
        raise ValueError("Workload must be between 0 and 100 percent")
    it = 20 + 80 * workload / 100
    cooling = it * (0.1 if liquid else 0.7)
    other = it * 0.1
    total = it + cooling + other
    return dict(it=it, cooling=cooling, other=other, total=total, pue=total / it)


def temperature(current: float, it_kw: float, liquid: bool, dt: float) -> float:
    # Lumped thermal model: C*dT/dt = Q - K*(T - coolant).
    # All electrical IT power becomes heat. Coolant stays at 22 C.
    conductance = 5.0 if liquid else 2.0  # kW / degree C
    capacity = 240.0  # kJ / degree C
    equilibrium = 22 + it_kw / conductance
    return equilibrium + (current - equilibrium) * exp(-conductance * dt / capacity)


@dataclass
class Simulation:
    seconds: float = 0
    air_temp: float = 30
    selected_temp: float = 30
    baseline_kwh: float = 0
    selected_kwh: float = 0
    history: list = field(default_factory=list)

    def step(self, workload: float, liquid: bool, dt: float = STEP_SECONDS):
        if dt <= 0:
            raise ValueError("Time step must be positive")
        air, selected = power(workload), power(workload, liquid)
        self.air_temp = temperature(self.air_temp, air['it'], False, dt)
        self.selected_temp = temperature(self.selected_temp, selected['it'], liquid, dt)
        self.seconds += dt
        self.baseline_kwh += air['total'] * dt / 3600
        self.selected_kwh += selected['total'] * dt / 3600
        self.history.append({
            'Time (min)': self.seconds / 60,
            'Traditional temperature (C)': self.air_temp,
            'Selected temperature (C)': self.selected_temp,
            'Traditional power (kW)': air['total'],
            'Selected power (kW)': selected['total'],
            'Energy saved (kWh)': self.baseline_kwh - self.selected_kwh,
            'Workload (%)': workload,
            'Liquid cooling': liquid,
        })
        self.history = self.history[-1800:]
