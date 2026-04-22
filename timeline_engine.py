"""
PRIPYAT-1986 Dual Timeline Engine
Manages two parallel timelines: historical (what happened) and intervened (what AI prevents).

The engine wraps EventSimulator + Orchestrator and produces combined tick payloads
for the web dashboard. When intervention is enabled and agents take action,
the intervened timeline branches using the physics model.
"""

from datetime import datetime
from dataclasses import asdict
from typing import Optional
from enum import Enum

from simulator import EventSimulator
from orchestrator import Orchestrator
from timeline_data import ReactorState
from physics import compute_scram_decay, compute_test_abort, compute_evacuation_progress
from config import SIMULATION


class DivergenceType(Enum):
    NONE = "none"
    SCRAM = "scram"
    ABORT = "abort"


class DualTimelineEngine:
    """
    Manages historical + intervened timelines.

    Before divergence: both timelines are identical.
    After divergence: historical continues from recorded events,
    intervened is computed by the physics model.
    """

    def __init__(self, speed: int = SIMULATION["speed_multiplier"]):
        self.simulator = EventSimulator(speed_multiplier=speed)
        self.orchestrator = Orchestrator()

        # Intervention state
        self.intervention_enabled = True
        self.diverged = False
        self.divergence_type = DivergenceType.NONE
        self.divergence_tick = None
        self.divergence_state: Optional[ReactorState] = None
        self.divergence_time: Optional[datetime] = None

        # Evacuation tracking
        self.evacuation_start_time: Optional[datetime] = None

        # Tick tracking
        self.current_tick = 0

    @property
    def total_ticks(self) -> int:
        return self.simulator.total_events

    def reset(self):
        """Reset everything to initial state."""
        self.simulator.reset()
        self.orchestrator.reset()
        self.diverged = False
        self.divergence_type = DivergenceType.NONE
        self.divergence_tick = None
        self.divergence_state = None
        self.divergence_time = None
        self.evacuation_start_time = None
        self.current_tick = 0

    def set_speed(self, speed: int):
        self.simulator.set_speed(speed)

    async def process_tick(self) -> Optional[dict]:
        """
        Process one tick. Returns combined payload for both timelines,
        or None if simulation is complete.
        """
        event = self.simulator.step()
        if event is None:
            return None

        self.current_tick = self.simulator.current_index
        progress_pct = self.current_tick / self.total_ticks * 100

        # Run agents on historical data (always)
        tick_summary = await self.orchestrator.process_tick(event)

        # Compute intervened state
        intervened_data = self._compute_intervened(event, tick_summary)

        # Check for evacuation progress
        evac_progress = None
        if self.evacuation_start_time:
            current_time = datetime.fromisoformat(event.timestamp)
            evac_elapsed = (current_time - self.evacuation_start_time).total_seconds()
            evac_progress = compute_evacuation_progress(evac_elapsed)

        # Build combined payload
        return {
            "type": "tick",
            "data": {
                "tick": self.current_tick,
                "timestamp": event.timestamp,
                "progress_pct": round(progress_pct, 1),
                "historical": {
                    "power_mw": event.power_mw,
                    "control_rods": event.control_rods_inserted,
                    "coolant_flow": event.coolant_flow_m3h,
                    "steam_pressure": event.steam_pressure_mpa,
                    "temperature_c": event.temperature_c,
                    "radiation": event.radiation_mrem_h,
                    "eccs_active": event.eccs_active,
                },
                "intervened": intervened_data,
                "risk_score": tick_summary["risk_score"],
                "alert_level": tick_summary["alert_level"],
                "sensor_alerts": tick_summary["sensor_alerts"],
                "decisions": tick_summary["decisions"],
                "actual_event": tick_summary["actual_event"],
                "actual_decision": tick_summary["actual_decision"],
                "counterfactual": tick_summary["counterfactual"],
                "dyatlov": tick_summary["dyatlov"],
                "state": {
                    **tick_summary["state"],
                    "intervention_enabled": self.intervention_enabled,
                    "diverged": self.diverged,
                    "divergence_tick": self.divergence_tick,
                    "divergence_type": self.divergence_type.value,
                },
                "evacuation_progress": evac_progress,
            },
        }

    def _compute_intervened(self, historical: ReactorState, tick_summary: dict) -> dict:
        """Compute the intervened timeline state."""

        # If not diverged yet, check if we should diverge
        if not self.diverged and self.intervention_enabled:
            for decision in tick_summary["decisions"]:
                action = decision["action"]
                if "SCRAM" in action or "SHUTDOWN" in action:
                    self._trigger_divergence(historical, DivergenceType.SCRAM)
                    break
                elif "ABORT TEST" in action:
                    self._trigger_divergence(historical, DivergenceType.ABORT)
                    break

            # Track evacuation start
            if tick_summary["state"]["evacuation_ordered"] and not self.evacuation_start_time:
                self.evacuation_start_time = datetime.fromisoformat(historical.timestamp)

        # Compute intervened state
        if self.diverged and self.divergence_state and self.divergence_time:
            current_time = datetime.fromisoformat(historical.timestamp)
            elapsed = (current_time - self.divergence_time).total_seconds()

            if self.divergence_type == DivergenceType.SCRAM:
                intervened = compute_scram_decay(self.divergence_state, elapsed)
            elif self.divergence_type == DivergenceType.ABORT:
                intervened = compute_test_abort(self.divergence_state, elapsed)
            else:
                intervened = historical

            return {
                "power_mw": intervened.power_mw,
                "control_rods": intervened.control_rods_inserted,
                "coolant_flow": intervened.coolant_flow_m3h,
                "steam_pressure": intervened.steam_pressure_mpa,
                "temperature_c": intervened.temperature_c,
                "radiation": intervened.radiation_mrem_h,
                "eccs_active": intervened.eccs_active,
                "diverged": True,
            }

        # Not diverged — mirror historical
        return {
            "power_mw": historical.power_mw,
            "control_rods": historical.control_rods_inserted,
            "coolant_flow": historical.coolant_flow_m3h,
            "steam_pressure": historical.steam_pressure_mpa,
            "temperature_c": historical.temperature_c,
            "radiation": historical.radiation_mrem_h,
            "eccs_active": historical.eccs_active,
            "diverged": False,
        }

    def _trigger_divergence(self, state: ReactorState, div_type: DivergenceType):
        """Record the point where the AI timeline diverges."""
        self.diverged = True
        self.divergence_type = div_type
        self.divergence_tick = self.current_tick
        self.divergence_state = state
        self.divergence_time = datetime.fromisoformat(state.timestamp)

    def get_final_report(self) -> dict:
        """Get the final comparison report."""
        report = self.orchestrator.get_final_report()
        report["intervention_enabled"] = self.intervention_enabled
        report["divergence"] = {
            "occurred": self.diverged,
            "type": self.divergence_type.value,
            "tick": self.divergence_tick,
            "timestamp": self.divergence_time.isoformat() if self.divergence_time else None,
        }
        return report
