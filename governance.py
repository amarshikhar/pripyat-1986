"""Decision authority boundaries for the PRIPYAT-1986 simulation.

The safety kernel is deliberately small, deterministic, and independent from
the LLM-backed agents.  It is the simulated equivalent of a safety instrumented
system (SIS): raw, validated telemetry can trip the reactor, while AI output
cannot.  Operational recommendations use a separate human-review lane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
from uuid import uuid4

from agents import AgentAction, AlertLevel
from config import THRESHOLDS
from timeline_data import ReactorState


ReviewStatus = Literal[
    "pending_review", "approved", "approved_with_edits", "rejected",
    # The plant moved on before a human answered (e.g. the deterministic
    # kernel already tripped the reactor this case proposed shutting down).
    "superseded",
]


@dataclass
class Recommendation:
    """An inert proposal awaiting one final, attributable human decision."""

    action: AgentAction
    id: str = field(default_factory=lambda: f"REC-{uuid4().hex[:10].upper()}")
    status: ReviewStatus = "pending_review"
    reviewer: str = ""
    note: str = ""
    reviewed_at: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "agent": self.action.metadata.get("origin_agent", self.action.agent),
            "action": self.action.action,
            "reasoning": self.action.reasoning,
            "level": self.action.alert_level.value,
            "source": self.action.metadata.get("source", "rule"),
            "reviewer": self.reviewer,
            "note": self.note,
            "reviewed_at": self.reviewed_at,
            "executed": bool(self.action.metadata.get("executed", False)),
        }


class SafetyKernel:
    """Independent hard-trip logic driven only by raw reactor telemetry.

    No risk score is accepted here because the displayed risk score can include
    an LLM contribution.  A safety trip must remain correct if the LLM is down,
    compromised, or confidently wrong.
    """

    name = "SafetyKernel"

    def __init__(self) -> None:
        self.reactor_scrammed = False

    def evaluate(self, state: ReactorState) -> Optional[AgentAction]:
        if self.reactor_scrammed:
            return None

        t = THRESHOLDS
        trip_reasons: list[str] = []

        if state.control_rods_inserted <= t["control_rods"]["critical_low"]:
            trip_reasons.append(
                f"operating reactivity margin lost ({state.control_rods_inserted} rods inserted)"
            )
        if state.coolant_flow_m3h <= t["coolant_flow_m3h"]["critical_low"]:
            trip_reasons.append(f"critical coolant flow ({state.coolant_flow_m3h:.0f} m³/h)")
        if state.steam_pressure_mpa >= t["steam_pressure_mpa"]["critical_high"]:
            trip_reasons.append(f"critical steam pressure ({state.steam_pressure_mpa:.2f} MPa)")
        if state.temperature_c >= t["temperature_c"]["critical_high"]:
            trip_reasons.append(f"critical core temperature ({state.temperature_c:.1f}°C)")

        # A disabled ECCS is not itself a trip in this counterfactual model, but
        # it removes the final barrier when operation is already outside the
        # approved low-power envelope.
        if (
            not state.eccs_active
            and state.power_mw <= t["power_mw"]["critical_low"]
        ):
            trip_reasons.append("ECCS unavailable during unsafe low-power operation")

        if not trip_reasons:
            return None

        self.reactor_scrammed = True
        return AgentAction(
            agent=self.name,
            timestamp=state.timestamp,
            action="AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
            reasoning="Deterministic protective trip: " + "; ".join(trip_reasons) + ".",
            alert_level=AlertLevel.EMERGENCY,
            metadata={
                "source": "safety_kernel",
                "status": "executed",
                "executed": True,
                "execution_authority": "deterministic_sis",
                "overridable": False,
                "trip_reasons": trip_reasons,
            },
        )

    def reset(self) -> None:
        self.reactor_scrammed = False
