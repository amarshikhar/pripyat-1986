"""
PRIPYAT-1986 Reactor Physics Model
Computes what happens after agent interventions (SCRAM, test abort, evacuation).

These are deterministic functions that take a ReactorState at the moment of
intervention and produce a new ReactorState at any future time offset.
"""

import math
from dataclasses import replace
from timeline_data import ReactorState
from config import EVACUATION, THRESHOLDS

# ── Physics Constants (RBMK-1000) ─────────────────────────────────
SCRAM_ROD_INSERTION_TIME_S = 18      # Full rod insertion takes ~18 seconds
POWER_DECAY_HALF_LIFE_S = 2.5       # Exponential power decay after SCRAM
COOLING_RATE_C_PER_MIN = 5.0        # Newton's cooling toward coolant temp
COOLANT_TARGET_TEMP_C = 180.0       # Coolant inlet temperature
NOMINAL_COOLANT_FLOW = 8000.0       # m³/h at full operation
ABORT_RAMP_DOWN_MW_PER_MIN = 5.0    # Controlled power reduction rate
TOTAL_RODS = 211                    # Total control rods in RBMK-1000


def compute_scram_decay(state: ReactorState, elapsed_s: float) -> ReactorState:
    """
    Compute reactor state after AZ-5 emergency shutdown (SCRAM).

    Physics:
    - Power decays exponentially with ~2.5s half-life
    - Control rods drive to full insertion over 18 seconds
    - Temperature drops via Newton's cooling law
    - Radiation stays at pre-SCRAM level (no core breach)
    - Coolant flow maintained/restored
    """
    # Power: exponential decay P(t) = P0 * (0.5)^(t / half_life)
    decay_factor = math.pow(0.5, elapsed_s / POWER_DECAY_HALF_LIFE_S)
    power = state.power_mw * decay_factor
    # Clamp to near-zero (decay heat remains ~7% initially, drops over hours)
    decay_heat_fraction = 0.07 * math.exp(-elapsed_s / 3600)  # Drops over ~1 hour
    power = max(state.power_mw * decay_heat_fraction, power)
    if power < 0.1:
        power = 0.0

    # Control rods: linear insertion over 18 seconds to full 211
    rod_progress = min(1.0, elapsed_s / SCRAM_ROD_INSERTION_TIME_S)
    rods = round(state.control_rods_inserted + (TOTAL_RODS - state.control_rods_inserted) * rod_progress)

    # Temperature: Newton's cooling toward coolant target
    temp_diff = state.temperature_c - COOLANT_TARGET_TEMP_C
    cooling_tau = 60.0 / COOLING_RATE_C_PER_MIN  # Time constant in seconds
    temperature = COOLANT_TARGET_TEMP_C + temp_diff * math.exp(-elapsed_s / (cooling_tau * 60))

    # Coolant flow: restored to nominal over ~60 seconds
    flow_recovery = min(1.0, elapsed_s / 60.0)
    coolant_flow = state.coolant_flow_m3h + (NOMINAL_COOLANT_FLOW - state.coolant_flow_m3h) * flow_recovery

    # Steam pressure: drops as power drops
    pressure_ratio = power / max(state.power_mw, 1.0)
    steam_pressure = max(0.0, state.steam_pressure_mpa * (0.3 + 0.7 * pressure_ratio))

    # Radiation: stays at pre-SCRAM level (no breach), slowly decreases
    radiation = state.radiation_mrem_h * math.exp(-elapsed_s / 7200)  # 2-hour decay

    # Compute simulated timestamp
    from datetime import datetime, timedelta
    base_time = datetime.fromisoformat(state.timestamp)
    new_time = base_time + timedelta(seconds=elapsed_s)

    return ReactorState(
        timestamp=new_time.strftime("%Y-%m-%dT%H:%M:%S"),
        power_mw=round(power, 1),
        control_rods_inserted=min(rods, TOTAL_RODS),
        coolant_flow_m3h=round(coolant_flow, 1),
        steam_pressure_mpa=round(steam_pressure, 2),
        temperature_c=round(temperature, 1),
        radiation_mrem_h=round(radiation, 4),
        eccs_active=True,  # ECCS re-enabled during SCRAM
        event_description="[AI INTERVENTION] Reactor SCRAM in progress — controlled shutdown.",
        actual_human_decision="[AI OVERRIDE] AZ-5 activated by AI Decision Agent.",
        tags=["ai_intervention", "scram"],
    )


def compute_test_abort(state: ReactorState, elapsed_s: float) -> ReactorState:
    """
    Compute reactor state after test abort — controlled power ramp-down.

    Physics:
    - Power decreases linearly at ~5 MW/min
    - Rods gradually inserted back to safe levels
    - Temperature and pressure decrease proportionally
    """
    elapsed_min = elapsed_s / 60.0

    # Power: linear ramp-down
    power = max(0.0, state.power_mw - ABORT_RAMP_DOWN_MW_PER_MIN * elapsed_min)

    # Rods: gradually insert toward safe minimum (140 for cold shutdown)
    target_rods = 140
    rod_rate_per_min = 3.0  # ~3 rods per minute
    rods = min(target_rods, round(state.control_rods_inserted + rod_rate_per_min * elapsed_min))

    # Temperature: gradual cooling
    power_ratio = power / max(state.power_mw, 1.0)
    temp_range = state.temperature_c - COOLANT_TARGET_TEMP_C
    temperature = COOLANT_TARGET_TEMP_C + temp_range * (0.2 + 0.8 * power_ratio)

    # Coolant flow maintained
    coolant_flow = min(NOMINAL_COOLANT_FLOW, state.coolant_flow_m3h + 50 * elapsed_min)

    # Steam pressure drops with power
    steam_pressure = max(0.0, state.steam_pressure_mpa * (0.3 + 0.7 * power_ratio))

    # Radiation stays background
    radiation = state.radiation_mrem_h

    from datetime import datetime, timedelta
    base_time = datetime.fromisoformat(state.timestamp)
    new_time = base_time + timedelta(seconds=elapsed_s)

    return ReactorState(
        timestamp=new_time.strftime("%Y-%m-%dT%H:%M:%S"),
        power_mw=round(power, 1),
        control_rods_inserted=min(rods, TOTAL_RODS),
        coolant_flow_m3h=round(coolant_flow, 1),
        steam_pressure_mpa=round(steam_pressure, 2),
        temperature_c=round(temperature, 1),
        radiation_mrem_h=round(radiation, 4),
        eccs_active=True,
        event_description="[AI INTERVENTION] Test aborted — controlled power reduction.",
        actual_human_decision="[AI OVERRIDE] Test cancelled by AI Decision Agent.",
        tags=["ai_intervention", "abort"],
    )


def compute_manual_state(control_rods: int, coolant_flow: float, eccs_active: bool) -> ReactorState:
    """
    Compute reactor state from operator control inputs using simplified RBMK physics.

    Inputs (what an operator actually controls):
    - control_rods: Number of rods inserted (0-211). Fewer rods = more reactivity.
    - coolant_flow: Primary coolant flow in m³/h (0-8000).
    - eccs_active: Emergency Core Cooling System on/off.

    Returns a ReactorState with derived telemetry (power, temp, pressure, radiation).

    The model is calibrated against the RBMK-1000 operating envelope in
    config.THRESHOLDS so that the manual lab has a usable safe region:

        rods=211, flow=8000  → 0 MW,    270 °C, 4.50 MPa   (shut down)
        rods=100, flow=8000  → 1007 MW, 278 °C, 5.13 MPa   (nominal, safe)
        rods=0,   flow=8000  → 3200 MW, 295 °C, 6.50 MPa   (rated power)
        rods=0,   flow=5000  → 3200 MW, 306 °C, 6.68 MPa   (warning band)
        rods=0,   flow=3000  → 3200 MW, 325 °C, 7.25 MPa   (hard-trip band)

    Warnings therefore appear *before* the deterministic SafetyKernel trips,
    which is what gives the human supervisor a window to accept or reject the
    agent's recommendation.
    """
    from datetime import datetime

    # Clamp inputs
    rods = max(0, min(TOTAL_RODS, int(control_rods)))
    coolant = max(0.0, min(NOMINAL_COOLANT_FLOW, float(coolant_flow)))
    eccs = bool(eccs_active)

    # Power: nonlinear reactivity from rod position
    # P = 3200 × (1 - rods/211)^1.8 — fewer rods = exponentially more power
    rod_fraction = rods / TOTAL_RODS
    power = 3200.0 * math.pow(max(0.0, 1.0 - rod_fraction), 1.8)
    heat = power / 3200.0

    # Temperature: heat balance — the core heats up with power and cools with
    # flow. Rated power at nominal flow sits just under the 300 °C warning line;
    # losing flow is what pushes the core into the danger band.
    effective_coolant = max(coolant, 500.0)  # Prevent division by near-zero
    cooling_deficit = math.pow(NOMINAL_COOLANT_FLOW / effective_coolant, 0.75)
    temperature = 270.0 + 25.0 * heat * cooling_deficit

    # ECCS off: the core loses its backup heat sink.
    if not eccs:
        temperature += 12.0 * heat

    # Steam pressure: rises with power, then sharply once the core runs hot.
    # 4.50 MPa idle → 6.50 MPa at rated power → past 7.50 MPa when overheating.
    steam_pressure = 4.5 + 2.0 * heat + max(0.0, temperature - 300.0) * 0.03

    # Radiation: background scales with power, spikes when the shutdown margin
    # is gone, and climbs steeply once the core is above its trip temperature
    # (fuel cladding damage).
    rod_spike = 50.0 if rods < THRESHOLDS["control_rods"]["critical_low"] else 0.0
    overheat = max(0.0, temperature - THRESHOLDS["temperature_c"]["critical_high"])
    radiation = 0.01 * (heat ** 2) * (1.0 + rod_spike) * (1.0 + (overheat / 40.0) ** 3)
    if not eccs:
        radiation *= 3.0

    # Clamp to reasonable ranges
    power = round(min(power, 50000.0), 1)
    temperature = round(min(temperature, 5000.0), 1)
    steam_pressure = round(min(steam_pressure, 20.0), 2)
    radiation = round(min(radiation, 100000.0), 4)

    return ReactorState(
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        power_mw=power,
        control_rods_inserted=rods,
        coolant_flow_m3h=round(coolant, 1),
        steam_pressure_mpa=steam_pressure,
        temperature_c=temperature,
        radiation_mrem_h=radiation,
        eccs_active=eccs,
        event_description=None,
        actual_human_decision=None,
        tags=["manual"],
    )


def compute_evacuation_progress(elapsed_s: float) -> dict:
    """
    Compute evacuation progress given time elapsed since order.

    Returns dict with people_evacuated, buses_in_transit, percent_complete, routes.
    """
    cfg = EVACUATION
    population = cfg["pripyat_population"]
    buses = cfg["buses_available"]
    capacity = cfg["bus_capacity"]
    elapsed_h = elapsed_s / 3600.0

    # Mobilization delay: 30 minutes before first buses depart
    MOBILIZATION_DELAY_H = 0.5
    if elapsed_h < MOBILIZATION_DELAY_H:
        return {
            "people_evacuated": 0,
            "buses_in_transit": 0,
            "percent_complete": 0.0,
            "phase": "MOBILIZING",
            "estimated_hours_remaining": 1.0,
            "routes": [],
        }

    active_hours = elapsed_h - MOBILIZATION_DELAY_H
    trip_time_h = 0.5  # 30 min per trip

    # Each bus makes trips continuously
    trips_per_bus = max(1, int(active_hours / trip_time_h))
    people_per_trip = buses * capacity
    total_evacuated = min(population, trips_per_bus * people_per_trip)
    percent = total_evacuated / population * 100

    # Buses currently in transit (between trips)
    in_transit = buses if percent < 100 else 0

    # Route breakdown
    route_data = []
    remaining = total_evacuated
    for route in cfg["routes"]:
        allocated = min(remaining, int(population * route["capacity_factor"] / 2.4))
        moved = min(allocated, total_evacuated * route["capacity_factor"] / 2.4)
        route_data.append({
            "name": route["name"],
            "distance_km": route["distance_km"],
            "people_moved": round(moved),
        })
        remaining -= round(moved)

    phase = "COMPLETE" if percent >= 100 else "IN PROGRESS"
    remaining_hours = max(0, (population - total_evacuated) / max(people_per_trip / trip_time_h, 1))

    return {
        "people_evacuated": total_evacuated,
        "buses_in_transit": in_transit,
        "percent_complete": round(min(100, percent), 1),
        "phase": phase,
        "estimated_hours_remaining": round(remaining_hours, 1),
        "routes": route_data,
    }
