"""
PRIPYAT-1986 Agent Implementations
5 specialized agents that form the crisis response system.

Each agent:
- Receives events from the message bus
- Uses AI reasoning (LLM) for decisions at key moments
- Falls back to rule-based logic when LLM unavailable
- Emits decisions/alerts back to the bus

CRoF (Control Room of the Future) Architecture:
- RiskAgent: AI-powered risk assessment with compound threat detection
- RecommendationAgent: AI-assisted recommendation drafting with mandatory review
- SensorAgent/EvacuationAgent/CommsAgent: Deterministic (legitimately rule-based)

Azure Migration:
- Replace LLM calls with Azure OpenAI / Semantic Kernel
- Replace message bus with Azure Event Hubs consumer groups
- Replace state files with Azure Cosmos DB
"""

import json
import math
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

from config import THRESHOLDS, RISK_CONFIG, EVACUATION, LLM_CONFIG, DYATLOV_CONFIG
from timeline_data import ReactorState, AI_COUNTERFACTUAL_DECISIONS
from llm_client import (
    LLMClient,
    RISK_ASSESSMENT_SCHEMA, DECISION_SCHEMA,
    RISK_SYSTEM_PROMPT, DECISION_SYSTEM_PROMPT,
    DYATLOV_SYSTEM_PROMPT, DYATLOV_OVERRIDE_SCHEMA,
)


# ── Message Types ──────────────────────────────────────────────────

class AlertLevel(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class AgentMessage:
    """Message passed between agents via the bus."""
    source: str
    target: str  # Agent name or "broadcast"
    msg_type: str
    timestamp: str
    payload: dict = field(default_factory=dict)
    alert_level: AlertLevel = AlertLevel.NORMAL


@dataclass
class AgentAction:
    """A decision or action taken by an agent."""
    agent: str
    timestamp: str
    action: str
    reasoning: str
    alert_level: AlertLevel = AlertLevel.NORMAL
    metadata: dict = field(default_factory=dict)


# ── AGENT 1: SENSOR MONITORING ────────────────────────────────────

class SensorAgent:
    """
    Ingests reactor telemetry and detects anomalies.
    Azure equivalent: Event Hubs consumer + anomaly detection model.
    """

    name = "SensorAgent"

    def __init__(self):
        self.alerts: list[AgentMessage] = []
        self.anomaly_count = 0

    def process(self, state: ReactorState) -> list[AgentMessage]:
        """Check all sensor readings against safety thresholds."""
        messages = []
        t = THRESHOLDS

        # Power level checks
        if state.power_mw <= t["power_mw"]["critical_low"]:
            messages.append(self._alert(
                state, AlertLevel.EMERGENCY,
                "POWER CRITICAL LOW",
                f"Reactor power at {state.power_mw} MW — below {t['power_mw']['critical_low']} MW. "
                f"Xenon poisoning imminent. SHUTDOWN REQUIRED.",
            ))
        elif state.power_mw <= t["power_mw"]["danger_low"]:
            messages.append(self._alert(
                state, AlertLevel.CRITICAL,
                "POWER DANGEROUSLY LOW",
                f"Power at {state.power_mw} MW — below safe minimum of {t['power_mw']['danger_low']} MW.",
            ))
        elif state.power_mw <= t["power_mw"]["test_target"] * 0.5:
            messages.append(self._alert(
                state, AlertLevel.WARNING,
                "POWER BELOW TEST TARGET",
                f"Power at {state.power_mw} MW — below test target of {t['power_mw']['test_target']} MW.",
            ))

        # Control rod checks
        if state.control_rods_inserted <= t["control_rods"]["critical_low"]:
            messages.append(self._alert(
                state, AlertLevel.EMERGENCY,
                "CONTROL RODS CRITICAL",
                f"Only {state.control_rods_inserted} rods inserted — below absolute minimum of "
                f"{t['control_rods']['critical_low']}. IMMEDIATE SCRAM REQUIRED.",
            ))
        elif state.control_rods_inserted <= t["control_rods"]["minimum_safe"]:
            messages.append(self._alert(
                state, AlertLevel.CRITICAL,
                "CONTROL RODS LOW",
                f"{state.control_rods_inserted} rods inserted — at or below minimum safe ({t['control_rods']['minimum_safe']}).",
            ))

        # ECCS check
        if not state.eccs_active:
            messages.append(self._alert(
                state, AlertLevel.CRITICAL,
                "ECCS DISABLED",
                "Emergency Core Cooling System is OFF. This removes the last safety barrier.",
            ))

        # Coolant flow
        if state.coolant_flow_m3h <= t["coolant_flow_m3h"]["critical_low"]:
            messages.append(self._alert(
                state, AlertLevel.EMERGENCY,
                "COOLANT FLOW CRITICAL",
                f"Coolant flow at {state.coolant_flow_m3h} m³/h — core overheating imminent.",
            ))
        elif state.coolant_flow_m3h <= t["coolant_flow_m3h"]["low_warning"]:
            messages.append(self._alert(
                state, AlertLevel.WARNING,
                "COOLANT FLOW LOW",
                f"Coolant flow at {state.coolant_flow_m3h} m³/h.",
            ))

        # Steam pressure
        if state.steam_pressure_mpa >= t["steam_pressure_mpa"]["critical_high"]:
            messages.append(self._alert(
                state, AlertLevel.EMERGENCY,
                "STEAM PRESSURE CRITICAL",
                f"Steam pressure at {state.steam_pressure_mpa} MPa — rupture risk.",
            ))

        # Radiation
        if state.radiation_mrem_h >= t["radiation_mrem_h"]["lethal_immediate"]:
            messages.append(self._alert(
                state, AlertLevel.EMERGENCY,
                "LETHAL RADIATION",
                f"Radiation at {state.radiation_mrem_h} mrem/h — immediately lethal.",
            ))
        elif state.radiation_mrem_h >= t["radiation_mrem_h"]["dangerous"]:
            messages.append(self._alert(
                state, AlertLevel.CRITICAL,
                "DANGEROUS RADIATION",
                f"Radiation at {state.radiation_mrem_h} mrem/h.",
            ))

        self.anomaly_count += len(messages)
        self.alerts.extend(messages)
        return messages

    def _alert(self, state: ReactorState, level: AlertLevel, title: str, detail: str) -> AgentMessage:
        return AgentMessage(
            source=self.name,
            target="RiskAgent",
            msg_type=title,
            timestamp=state.timestamp,
            alert_level=level,
            payload={"detail": detail, "power_mw": state.power_mw,
                     "rods": state.control_rods_inserted, "eccs": state.eccs_active},
        )


# ── AGENT 2: RISK ASSESSMENT (AI-POWERED) ────────────────────────

class RiskAgent:
    """
    AI-powered risk assessment agent.
    Uses LLM to detect compound risks and rate-of-change patterns that
    simple threshold formulas miss. Falls back to rule-based scoring.

    CRoF Role: Real-time N-1 contingency analysis (NERC TPL-001 equivalent).
    Azure equivalent: Azure AI Search over IAEA safety knowledge base.
    """

    name = "RiskAgent"
    LLM_COOLDOWN_TICKS = 5  # Min ticks between LLM calls when alerts persist

    def __init__(self, llm_client: Optional['LLMClient'] = None):
        self.current_score = 0
        self.score_history: list[tuple[str, int]] = []
        self.previous_state: Optional[ReactorState] = None
        self.llm = llm_client
        self.last_llm_reasoning: Optional[str] = None
        self._last_llm_tick: int = -999  # Last tick we called LLM
        self._last_alert_level: Optional[AlertLevel] = None  # Track alert escalation
        self._evacuation_done: bool = False  # Stop LLM after evacuation ordered

    def _is_decision_point(self, state: ReactorState, rule_score: int,
                            sensor_alerts: list[AgentMessage] = None) -> bool:
        """Determine if this tick warrants an LLM call."""
        if not LLM_CONFIG.get("decision_points_only", True):
            return True
        # Post-evacuation: no LLM needed, rules suffice for monitoring
        if self._evacuation_done:
            return False
        # Skip LLM calls entirely for manual-mode ticks (including post-SCRAM)
        if state.tags and "manual" in state.tags:
            # Post-SCRAM: physics drives decay — LLM would inflate the score
            if "scram" in state.tags:
                return False
            prev_score = self.score_history[-1][1] if self.score_history else 0
            for boundary in [30, 60, 85]:
                if (prev_score < boundary <= rule_score) or (rule_score < boundary <= prev_score):
                    return True
            return False
        # Real timeline event (tagged in INSAG-7 data) — ALWAYS call LLM
        if state.tags:
            return True
        if state.event_description:
            return True
        # ── Interpolated ticks below: apply global cooldown ──
        current_tick = len(self.score_history) + 1
        within_cooldown = (current_tick - self._last_llm_tick) < self.LLM_COOLDOWN_TICKS
        # Alert level escalation overrides cooldown
        if sensor_alerts:
            has_emergency = any(a.alert_level == AlertLevel.EMERGENCY for a in sensor_alerts)
            has_critical = any(
                a.alert_level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)
                for a in sensor_alerts
            )
            if has_critical:
                max_level = AlertLevel.EMERGENCY if has_emergency else AlertLevel.CRITICAL
                # Escalation to a NEW severity level always triggers
                if self._last_alert_level != max_level:
                    return True
        # If within cooldown, skip everything else
        if within_cooldown:
            return False
        # Risk score crossed a threshold boundary
        prev_score = self.score_history[-1][1] if self.score_history else 0
        for boundary in [30, 60, 85]:
            if (prev_score < boundary <= rule_score) or (rule_score < boundary <= prev_score):
                return True
        # CRITICAL/EMERGENCY alerts — call at cooldown interval
        if sensor_alerts:
            has_critical = any(
                a.alert_level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)
                for a in sensor_alerts
            )
            if has_critical:
                return True
        return False

    def _rule_based_score(self, state: ReactorState) -> tuple[int, dict]:
        """Compute deterministic risk score (used as baseline + fallback)."""
        t = THRESHOLDS
        w = RISK_CONFIG["weights"]
        scores = {}

        # After SCRAM, low power / high rods is the DESIRED safe state
        post_scram = state.tags and "scram" in state.tags

        # Power anomaly score
        power = state.power_mw
        if post_scram:
            # After SCRAM: power dropping is good. Only worry about unexpected surges.
            if power > 500 and state.control_rods_inserted < 30:
                scores["power_anomaly"] = 100  # Power NOT dropping = real danger
            else:
                scores["power_anomaly"] = 0  # Decaying power = expected
        elif power <= t["power_mw"]["critical_low"]:
            scores["power_anomaly"] = 100
        elif power <= t["power_mw"]["danger_low"]:
            scores["power_anomaly"] = 80
        elif power <= t["power_mw"]["test_target"]:
            scores["power_anomaly"] = 40
        else:
            scores["power_anomaly"] = max(0, (t["power_mw"]["nominal"] - power) / t["power_mw"]["nominal"] * 20)

        # Surge detection (power going UP uncontrollably)
        if not post_scram and power > 500 and state.control_rods_inserted < 15:
            scores["power_anomaly"] = 100

        # Rod position score
        rods = state.control_rods_inserted
        if post_scram:
            # After SCRAM: rods driving to 211 is correct behavior
            scores["rod_position"] = 0
        elif rods <= t["control_rods"]["critical_low"]:
            scores["rod_position"] = 100
        elif rods <= t["control_rods"]["minimum_safe"]:
            scores["rod_position"] = 70
        else:
            scores["rod_position"] = max(0, (100 - rods) / 100 * 30)

        # Coolant score
        coolant = state.coolant_flow_m3h
        if coolant <= t["coolant_flow_m3h"]["critical_low"]:
            scores["coolant_anomaly"] = 100
        elif coolant <= t["coolant_flow_m3h"]["low_warning"]:
            scores["coolant_anomaly"] = 60
        else:
            scores["coolant_anomaly"] = 0

        # Steam pressure score
        steam = state.steam_pressure_mpa
        if steam >= t["steam_pressure_mpa"]["critical_high"]:
            scores["steam_pressure"] = 100
        elif steam >= t["steam_pressure_mpa"]["high_warning"]:
            scores["steam_pressure"] = 60
        else:
            scores["steam_pressure"] = 0

        # Temperature score
        temp = state.temperature_c
        if temp >= t["temperature_c"]["critical_high"]:
            scores["temperature"] = 100
        elif temp >= t["temperature_c"]["high_warning"]:
            scores["temperature"] = 60
        else:
            scores["temperature"] = 0

        # Radiation score
        rad = state.radiation_mrem_h
        if rad >= t["radiation_mrem_h"]["lethal_immediate"]:
            scores["radiation"] = 100
        elif rad >= t["radiation_mrem_h"]["dangerous"]:
            scores["radiation"] = 80
        elif rad >= t["radiation_mrem_h"]["elevated"]:
            scores["radiation"] = 40
        else:
            scores["radiation"] = 0

        # ECCS penalty — adds 15 points if disabled
        eccs_penalty = 15 if not state.eccs_active else 0

        # Rate-of-change penalty: rapid power decline toward danger zone
        rate_penalty = 0
        if self.previous_state and not post_scram:
            power_delta = state.power_mw - self.previous_state.power_mw
            # Penalize rapid power drop when already below test target
            if power_delta < -20 and state.power_mw < t["power_mw"]["test_target"]:
                rate_penalty = min(20, abs(power_delta) / 3)
            # Extra penalty for rod withdrawal during power decline
            rod_delta = state.control_rods_inserted - self.previous_state.control_rods_inserted
            if rod_delta < 0 and state.power_mw < t["power_mw"]["danger_low"]:
                rate_penalty += min(10, abs(rod_delta) * 2)

        # Compound violation multiplier
        violations = sum(1 for s in scores.values() if s >= 60)
        compound_mult = 1.0 + (violations * 0.15)

        raw = sum(scores.get(k, 0) * v for k, v in w.items()) + eccs_penalty + rate_penalty
        total = raw * compound_mult
        rule_score = min(100, round(total))

        # Severity floor. The weighted average dilutes a single parameter that
        # is far outside its band — a core at 330 °C is not a "12/100" plant just
        # because every other reading is nominal. The floor keeps the gauge
        # honest without letting one warning saturate it.
        if not post_scram:
            worst = max(scores.values(), default=0)
            if worst >= 100:
                rule_score = max(rule_score, 70)
            elif worst >= 60:
                rule_score = max(rule_score, 35)

        return rule_score, scores

    async def _llm_risk_assessment(self, state: ReactorState, rule_score: int, scores: dict,
                              sensor_alerts: list[AgentMessage]) -> Optional[dict]:
        """Call LLM for AI risk assessment."""
        if not self.llm or not self.llm.available:
            return None

        # Build rate-of-change context
        delta_info = ""
        if self.previous_state:
            prev = self.previous_state
            delta_info = (
                f"\nRATE OF CHANGE (since {prev.timestamp}):\n"
                f"- Power: {prev.power_mw} → {state.power_mw} MW (delta: {state.power_mw - prev.power_mw:+.0f})\n"
                f"- Rods: {prev.control_rods_inserted} → {state.control_rods_inserted} (delta: {state.control_rods_inserted - prev.control_rods_inserted:+d})\n"
                f"- Coolant: {prev.coolant_flow_m3h} → {state.coolant_flow_m3h} m³/h (delta: {state.coolant_flow_m3h - prev.coolant_flow_m3h:+.0f})\n"
                f"- Radiation: {prev.radiation_mrem_h} → {state.radiation_mrem_h} mrem/h\n"
            )

        alert_summary = "; ".join(
            f"[{a.alert_level.value}] {a.msg_type}"
            for a in sensor_alerts[:6]
        ) or "None"

        user_prompt = (
            f"REACTOR TELEMETRY at {state.timestamp}:\n"
            f"- Power: {state.power_mw} MW (rated: 3200 MW, test target: 700 MW)\n"
            f"- Control rods inserted: {state.control_rods_inserted}/211 (minimum safe: 30)\n"
            f"- Coolant flow: {state.coolant_flow_m3h} m³/h (nominal: 8000)\n"
            f"- Steam pressure: {state.steam_pressure_mpa} MPa (nominal: 6.5)\n"
            f"- Core temperature: {state.temperature_c}°C (nominal: 280)\n"
            f"- Radiation: {state.radiation_mrem_h} mrem/h (background: 0.01)\n"
            f"- ECCS: {'ACTIVE' if state.eccs_active else 'DISABLED'}\n"
            f"{delta_info}\n"
            f"SENSOR ALERTS: {alert_summary}\n"
            f"RULE-BASED SCORE: {rule_score}/100\n"
            f"CURRENT EVENT: {state.event_description or 'Interpolated tick'}\n"
            f"OPERATOR ACTION: {state.actual_human_decision or 'N/A'}\n\n"
            f"Assess the overall risk. Consider compound effects and rate-of-change."
        )

        return await self.llm.call_structured(
            system_prompt=RISK_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=RISK_ASSESSMENT_SCHEMA,
            schema_name="risk_assessment",
            temperature=LLM_CONFIG.get("temperature_risk", 0.3),
            max_tokens=LLM_CONFIG.get("max_tokens_risk", 250),
        )

    async def process(self, state: ReactorState, sensor_alerts: list[AgentMessage]) -> tuple[int, AgentMessage]:
        """Calculate risk score using AI + rule-based blending."""
        # Step 1: Always compute rule-based score (baseline)
        rule_score, scores = self._rule_based_score(state)

        # Step 2: Call LLM at decision points for AI assessment
        source = "rule"
        ai_reasoning = None
        llm_data = None

        if self._is_decision_point(state, rule_score, sensor_alerts):
            llm_data = await self._llm_risk_assessment(state, rule_score, scores, sensor_alerts)
            if llm_data:
                # Track cooldown state
                self._last_llm_tick = len(self.score_history) + 1
                if sensor_alerts:
                    levels = [a.alert_level for a in sensor_alerts
                              if a.alert_level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)]
                    _severity = {AlertLevel.CRITICAL: 1, AlertLevel.EMERGENCY: 2}
                    self._last_alert_level = max(levels, key=lambda l: _severity.get(l, 0), default=None) if levels else None

        if llm_data:
            # Blend: 70% AI + 30% rule-based
            llm_score = max(0, min(100, llm_data.get("risk_score", rule_score)))
            self.current_score = round(0.7 * llm_score + 0.3 * rule_score)
            ai_reasoning = llm_data.get("reasoning", "")
            self.last_llm_reasoning = ai_reasoning
            source = "llm"
        else:
            self.current_score = rule_score
            self.last_llm_reasoning = None

        # Asymmetric EMA smoothing — applied to ALL ticks so the score never zigzags.
        # Risk rises quickly (danger must be visible fast) but falls slowly (recovery is gradual).
        # Post-SCRAM: fast decay — physics is already shutting down the reactor.
        if self.score_history:
            prev_score = self.score_history[-1][1]
            post_scram_ema = bool(state.tags and "scram" in state.tags)
            manual_ema = bool(state.tags and "manual" in state.tags)
            if self.current_score > prev_score:
                alpha = 0.45  # Rising: react to escalation within ~2 ticks
            elif post_scram_ema:
                alpha = 0.40  # Post-SCRAM falling: reach normal in ~5 ticks
            elif manual_ema:
                # Manual lab: the operator moved a lever, so recovery must be
                # visible on the gauge within a few seconds, not ~15 ticks.
                alpha = 0.35
            else:
                alpha = 0.15  # Normal falling: gradual recovery over ~15 ticks
            self.current_score = round(alpha * self.current_score + (1 - alpha) * prev_score)

        self.score_history.append((state.timestamp, self.current_score))
        self.previous_state = state

        # Determine alert level
        if self.current_score >= RISK_CONFIG["escalation_threshold"]:
            level = AlertLevel.EMERGENCY
        elif self.current_score >= RISK_CONFIG["warning_threshold"]:
            level = AlertLevel.CRITICAL
        elif self.current_score >= 30:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.NORMAL

        payload = {
            "risk_score": self.current_score,
            "rule_score": rule_score,
            "component_scores": scores,
            "num_sensor_alerts": len(sensor_alerts),
            "source": source,
        }
        if llm_data:
            payload["ai_trend"] = llm_data.get("trend", "unknown")
            payload["ai_primary_concern"] = llm_data.get("primary_concern", "")
            payload["ai_compound_risks"] = llm_data.get("compound_risks", [])
            payload["ai_recommendation"] = llm_data.get("recommendation", "")
            payload["ai_reasoning"] = ai_reasoning

        msg = AgentMessage(
            source=self.name,
            target="RecommendationAgent",
            msg_type="RISK_SCORE",
            timestamp=state.timestamp,
            alert_level=level,
            payload=payload,
        )

        return self.current_score, msg


# ── AGENT 3: DECISION ORCHESTRATOR (AI-POWERED) ─────────────────

# Map LLM action strings to internal action names
_LLM_ACTION_MAP = {
    "SCRAM": "AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
    "EVACUATE": "ORDER IMMEDIATE EVACUATION OF PRIPYAT",
    "ABORT_TEST": "ABORT TEST",
    "WARN_ECCS": "ECCS VIOLATION WARNING",
    "CONTINUE_MONITORING": None,  # No action needed
}

_LLM_URGENCY_TO_LEVEL = {
    "immediate": AlertLevel.EMERGENCY,
    "high": AlertLevel.CRITICAL,
    "medium": AlertLevel.WARNING,
    "low": AlertLevel.NORMAL,
}


class RecommendationAgent:
    """
    AI recommendation agent.

    It can explain risk and draft proposed actions, but it has no actuator
    authority. Every returned action is marked ``pending_review`` and must be
    resolved by a human supervisor. The independent deterministic
    ``SafetyKernel`` owns hard protective trips; keeping that kernel outside
    the agent prevents an LLM score or prompt from becoming a safety control.

    CRoF Role: operator decision-support and recommendation drafting.
    Azure equivalent: Microsoft Agent Framework with Semantic Kernel.
    """

    name = "RecommendationAgent"
    LLM_COOLDOWN_TICKS = 5  # Min ticks between LLM calls when alerts persist

    def __init__(self, llm_client: Optional['LLMClient'] = None):
        self.decisions: list[AgentAction] = []
        self.reactor_scrammed = False
        self.evacuation_ordered = False
        self.llm = llm_client
        self._last_llm_tick: int = -999
        self._last_alert_level: Optional[AlertLevel] = None

    def _is_decision_point(self, state: ReactorState, risk_score: int,
                            sensor_alerts: list[AgentMessage] = None) -> bool:
        """Determine if this tick warrants an LLM recommendation call."""
        if not LLM_CONFIG.get("decision_points_only", True):
            return True
        # Skip LLM in manual mode (including post-SCRAM decay)
        if state.tags and "manual" in state.tags:
            return False
        # Real timeline event (not interpolation) — ALWAYS call LLM
        if state.tags:
            return True
        if state.event_description:
            return True
        # Risk above warning threshold — with cooldown to avoid flooding
        if risk_score >= RISK_CONFIG["warning_threshold"]:
            if self._ticks_since_last_llm() >= self.LLM_COOLDOWN_TICKS:
                return True
            return False
        # CRITICAL or EMERGENCY sensor alerts — with cooldown
        if sensor_alerts:
            crisis_levels = [
                a.alert_level for a in sensor_alerts
                if a.alert_level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)
            ]
            if crisis_levels:
                _severity = {AlertLevel.CRITICAL: 1, AlertLevel.EMERGENCY: 2}
                max_level = max(crisis_levels, key=lambda l: _severity.get(l, 0))
                # Call on first occurrence or level escalation
                if self._last_alert_level != max_level:
                    return True
                # Cooldown: don't call LLM every tick
                if self._ticks_since_last_llm() >= self.LLM_COOLDOWN_TICKS:
                    return True
        return False

    def _ticks_since_last_llm(self) -> int:
        """How many decisions have been made since last LLM call."""
        return len(self.decisions) - self._last_llm_tick if self._last_llm_tick >= 0 else 999

    def _rule_based_recommendations(self, state: ReactorState, risk_score: int,
                            sensor_alerts: list[AgentMessage] = None,
                            commanded_state: Optional[ReactorState] = None) -> list[AgentAction]:
        """Deterministic recommendation rules; outputs remain inert."""
        actions = []
        counterfactual = AI_COUNTERFACTUAL_DECISIONS.get(state.timestamp)

        # PROPOSAL RULE 1: recommend emergency shutdown if risk > 85
        if risk_score >= RISK_CONFIG["escalation_threshold"] and not self.reactor_scrammed:
            reasoning = self._fallback_reasoning(state, risk_score)
            actions.append(AgentAction(
                agent=self.name,
                timestamp=state.timestamp,
                action="AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
                reasoning=reasoning,
                alert_level=AlertLevel.EMERGENCY,
                metadata={
                    "risk_score": risk_score,
                    "counterfactual": counterfactual,
                    "review_authority": "human_supervisor",
                    "source": "rule",
                },
            ))

        # PROPOSAL RULE 2: compound violation recommendation. The independent
        # SafetyKernel separately evaluates whether raw telemetry requires a trip.
        if not self.reactor_scrammed and not state.eccs_active and sensor_alerts:
            has_emergency = any(
                a.alert_level == AlertLevel.EMERGENCY
                for a in sensor_alerts
            )
            if has_emergency:
                actions.append(AgentAction(
                    agent=self.name,
                    timestamp=state.timestamp,
                    action="AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
                    reasoning=(
                        f"Compound violation: EMERGENCY sensor alert with ECCS disabled. "
                        f"No safety barriers remain. INSAG-7 mandates immediate shutdown."
                    ),
                    alert_level=AlertLevel.EMERGENCY,
                    metadata={
                        "risk_score": risk_score,
                        "trigger": "compound_eccs_emergency",
                        "counterfactual": counterfactual,
                        "review_authority": "human_supervisor",
                        "source": "rule",
                    },
                ))

        # PROPOSAL RULE 2b: warning-band triage.
        # The agent watches the warning band, which sits below every SafetyKernel
        # hard-trip limit, and asks the supervisor to decide while there is still
        # a decision to make. In the manual lab it also reads the *commanded*
        # lever positions, so the case opens while the reactor is still ramping
        # toward them rather than after the kernel has already tripped.
        already_proposing_scram = any(
            a.action == "AZ-5 EMERGENCY SHUTDOWN (SCRAM)" for a in actions
        )
        if not self.reactor_scrammed and not already_proposing_scram:
            crossings, escalate = self._threshold_crossings(state, risk_score)
            if commanded_state is not None:
                commanded_crossings, commanded_escalate = self._threshold_crossings(
                    commanded_state, risk_score,
                )
                new_crossings = [c for c in commanded_crossings if c not in crossings]
                if new_crossings:
                    crossings = crossings + [
                        f"operator has commanded a configuration that reaches: "
                        + "; ".join(new_crossings)
                    ]
                escalate = escalate or commanded_escalate
            if escalate:
                actions.append(AgentAction(
                    agent=self.name,
                    timestamp=state.timestamp,
                    action="AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
                    reasoning=(
                        "Plant is outside its safe operating envelope: "
                        + "; ".join(crossings)
                        + f". Risk {risk_score}/100. Recommending AZ-5 before the deterministic "
                          "safety kernel is forced to trip. No action is taken until a supervisor "
                          "approves or rejects this recommendation."
                    ),
                    alert_level=AlertLevel.CRITICAL,
                    metadata={
                        "risk_score": risk_score,
                        "trigger": "threshold_crossing",
                        "threshold_crossings": crossings,
                        "review_authority": "human_supervisor",
                        "source": "rule",
                    },
                ))

        # PROPOSAL RULE 3: recommend evacuation if radiation is dangerous
        if (state.radiation_mrem_h >= THRESHOLDS["radiation_mrem_h"]["dangerous"]
                and not self.evacuation_ordered):
            actions.append(AgentAction(
                agent=self.name,
                timestamp=state.timestamp,
                action="ORDER IMMEDIATE EVACUATION OF PRIPYAT",
                reasoning=(
                    f"Radiation at {state.radiation_mrem_h} mrem/h confirms core breach. "
                    f"49,000 residents at immediate risk. Wind direction NW → fallout over city. "
                    f"Every hour of delay = increased population dose."
                ),
                alert_level=AlertLevel.EMERGENCY,
                metadata={"trigger": "radiation_threshold", "source": "rule"},
            ))

        return actions

    @staticmethod
    def _threshold_crossings(state: ReactorState, risk_score: int) -> tuple[list[str], bool]:
        """Warning-band threshold crossings, described in operator language.

        Returns the crossings plus whether they warrant a supervisor case.

        Every limit here is deliberately *looser* than the matching SafetyKernel
        hard-trip limit, so the human review window opens before the trip. One
        mild warning on an otherwise healthy plant is monitored, not escalated;
        a case is opened when two bands are breached at once or when a single
        reading is closing on its trip limit.
        """
        t = THRESHOLDS
        crossings: list[str] = []
        proximate = False

        if state.control_rods_inserted <= t["control_rods"]["minimum_safe"]:
            crossings.append(
                f"shutdown margin below minimum ({state.control_rods_inserted}/211 rods inserted, "
                f"minimum safe {t['control_rods']['minimum_safe']})"
            )
            proximate |= state.control_rods_inserted <= t["control_rods"]["critical_low"] + 5
        if state.coolant_flow_m3h <= t["coolant_flow_m3h"]["low_warning"]:
            crossings.append(
                f"coolant flow {state.coolant_flow_m3h:.0f} m³/h below "
                f"{t['coolant_flow_m3h']['low_warning']:.0f} m³/h"
            )
            proximate |= state.coolant_flow_m3h <= t["coolant_flow_m3h"]["critical_low"] * 1.2
        if state.temperature_c >= t["temperature_c"]["high_warning"]:
            crossings.append(
                f"core temperature {state.temperature_c:.0f}°C above "
                f"{t['temperature_c']['high_warning']}°C"
            )
            proximate |= state.temperature_c >= t["temperature_c"]["critical_high"] - 8
        if state.steam_pressure_mpa >= t["steam_pressure_mpa"]["high_warning"]:
            crossings.append(
                f"steam pressure {state.steam_pressure_mpa:.2f} MPa above "
                f"{t['steam_pressure_mpa']['high_warning']} MPa"
            )
            proximate |= state.steam_pressure_mpa >= t["steam_pressure_mpa"]["critical_high"] - 0.2
        if state.radiation_mrem_h >= t["radiation_mrem_h"]["elevated"]:
            crossings.append(f"radiation elevated at {state.radiation_mrem_h:.2f} mrem/h")
            proximate |= state.radiation_mrem_h >= t["radiation_mrem_h"]["dangerous"]
        if 0 < state.power_mw <= t["power_mw"]["danger_low"]:
            # The 1986 accident turned here: a power collapse into the xenon
            # band is recoverable only by shutting down, and the deterministic
            # kernel will not trip until power reaches critical_low with the
            # ECCS already gone. This is the last point a human can still choose.
            crossings.append(
                f"power {state.power_mw:.0f} MW inside the xenon-poisoning band "
                f"(below {t['power_mw']['danger_low']} MW)"
            )
            proximate = True
        if not state.eccs_active:
            # The last cooling barrier is gone while the core is still fuelled.
            crossings.append(f"ECCS disabled while the core is at {state.power_mw:.0f} MW")
            proximate = True
        if risk_score >= RISK_CONFIG["warning_threshold"]:
            crossings.append(f"composite risk {risk_score}/100 at or above the review threshold")
            proximate = True

        return crossings, (proximate or len(crossings) >= 2)

    async def _llm_recommend(self, state: ReactorState, risk_score: int,
                     sensor_alerts: list[AgentMessage]) -> Optional[dict]:
        """Call LLM for a structured decision."""
        if not self.llm or not self.llm.available:
            return None

        alert_summary = "; ".join(
            f"[{a.alert_level.value}] {a.msg_type}: {a.payload.get('detail', '')}"
            for a in sensor_alerts[:6]
        ) or "None"

        # Include previous decisions for context
        prev_decisions = "; ".join(
            f"{d.action} at {d.timestamp}" for d in self.decisions[-3:]
        ) or "None yet"

        user_prompt = (
            f"REACTOR STATE at {state.timestamp}:\n"
            f"- Power: {state.power_mw} MW (rated: 3200 MW, test target: 700 MW)\n"
            f"- Control rods: {state.control_rods_inserted}/211 (minimum safe: 30, critical: 15)\n"
            f"- Coolant flow: {state.coolant_flow_m3h} m³/h (nominal: 8000)\n"
            f"- Steam pressure: {state.steam_pressure_mpa} MPa (nominal: 6.5)\n"
            f"- Core temperature: {state.temperature_c}°C (nominal: 280)\n"
            f"- Radiation: {state.radiation_mrem_h} mrem/h (background: 0.01)\n"
            f"- ECCS: {'ACTIVE' if state.eccs_active else 'DISABLED'}\n\n"
            f"RISK SCORE: {risk_score}/100\n"
            f"ACTIVE ALERTS: {alert_summary}\n"
            f"CURRENT EVENT: {state.event_description or 'Routine monitoring'}\n"
            f"OPERATOR ACTION: {state.actual_human_decision or 'N/A'}\n"
            f"PREVIOUS AI DECISIONS: {prev_decisions}\n"
            f"REACTOR SCRAMMED: {self.reactor_scrammed}\n"
            f"EVACUATION ORDERED: {self.evacuation_ordered}\n\n"
            f"What should the supervisor review? Provide one evidence-grounded recommendation."
        )

        return await self.llm.call_structured(
            system_prompt=DECISION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=DECISION_SCHEMA,
            schema_name="decision",
            temperature=LLM_CONFIG.get("temperature_decision", 0.2),
            max_tokens=LLM_CONFIG.get("max_tokens_decision", 300),
        )

    def _llm_actions_from_response(self, llm_data: dict, state: ReactorState,
                                     risk_score: int) -> list[AgentAction]:
        """Convert LLM structured response into AgentActions."""
        actions = []
        action_str = llm_data.get("action", "CONTINUE_MONITORING")
        mapped_action = _LLM_ACTION_MAP.get(action_str)

        if not mapped_action:
            return actions  # CONTINUE_MONITORING = no action

        # Sanity guardrail: LLM cannot trigger SCRAM/ABORT when risk is low
        # ABORT_TEST also requires power to have actually dropped — prevents LLM
        # from calling abort during the safe preparation phase (18:00-23:00)
        if action_str == "SCRAM" and risk_score < 60:
            return actions
        if action_str == "ABORT_TEST" and (risk_score < 55 or state.power_mw > 900):
            return actions

        # Check if we already have this action (avoid duplicates)
        if mapped_action == "AZ-5 EMERGENCY SHUTDOWN (SCRAM)" and self.reactor_scrammed:
            return actions
        if mapped_action == "ORDER IMMEDIATE EVACUATION OF PRIPYAT" and self.evacuation_ordered:
            return actions
        if any(d.action == mapped_action for d in self.decisions):
            return actions

        urgency = llm_data.get("urgency", "medium")
        level = _LLM_URGENCY_TO_LEVEL.get(urgency, AlertLevel.WARNING)
        reasoning = llm_data.get("reasoning", "AI recommendation")
        counterfactual = AI_COUNTERFACTUAL_DECISIONS.get(state.timestamp)

        actions.append(AgentAction(
            agent=self.name,
            timestamp=state.timestamp,
            action=mapped_action,
            reasoning=reasoning,
            alert_level=level,
            metadata={
                "risk_score": risk_score,
                "source": "llm",
                "counterfactual": counterfactual,
                "safety_violations": llm_data.get("safety_violations", []),
                "human_review_required": llm_data.get("human_review_required", True),
                "additional_actions": llm_data.get("additional_actions", []),
            },
        ))

        return actions

    async def process(
        self, state: ReactorState, risk_score: int, sensor_alerts: list[AgentMessage],
        commanded_state: Optional[ReactorState] = None,
    ) -> list[AgentAction]:
        """
        Draft recommendations. This method never changes plant state.

        ``commanded_state`` is where the operator's levers are pointing, which
        the plant is still ramping toward. Reading it lets the agent open a case
        early enough for a human to actually answer it.
        """
        # Step 1: deterministic proposal rules (still no actuator authority)
        rule_proposals = self._rule_based_recommendations(
            state, risk_score, sensor_alerts, commanded_state,
        )

        # Step 2: AI recommendation at decision points
        llm_actions = []
        if self._is_decision_point(state, risk_score, sensor_alerts) and not self.reactor_scrammed:
            llm_data = await self._llm_recommend(state, risk_score, sensor_alerts)
            if llm_data:
                llm_actions = self._llm_actions_from_response(llm_data, state, risk_score)
                # Track cooldown
                self._last_llm_tick = len(self.decisions)
                if sensor_alerts:
                    levels = [a.alert_level for a in sensor_alerts
                              if a.alert_level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY)]
                    _severity = {AlertLevel.CRITICAL: 1, AlertLevel.EMERGENCY: 2}
                    self._last_alert_level = max(levels, key=lambda l: _severity.get(l, 0), default=None) if levels else None

        # Step 3: merge rule and LLM proposals (no duplicates)
        rule_action_names = {a.action for a in rule_proposals}
        merged = list(rule_proposals)
        for la in llm_actions:
            if la.action not in rule_action_names:
                merged.append(la)

        # Step 4: Fallback — if no LLM and no guardrail triggered, check rule-based extras
        if not llm_actions and not rule_proposals:
            merged.extend(self._rule_based_extras(state))

        # Step 5: proposals are inert until the orchestrator records a human
        # decision. The metadata is the enforcement boundary used by every
        # downstream consumer.
        for action in merged:
            action.agent = self.name
            action.metadata.update({
                "status": "pending_review",
                "execution_authority": "human_supervisor",
                "executed": False,
            })

        self.decisions.extend(merged)
        return merged

    def _rule_based_extras(self, state: ReactorState) -> list[AgentAction]:
        """Additional rule-based checks (ECCS warning, abort test) as fallback."""
        actions = []

        # Warn about ECCS
        if not state.eccs_active and not self.reactor_scrammed:
            if not any(a.action == "ECCS VIOLATION WARNING" for a in self.decisions):
                actions.append(AgentAction(
                    agent=self.name,
                    timestamp=state.timestamp,
                    action="ECCS VIOLATION WARNING",
                    reasoning=(
                        "Emergency Core Cooling System disabled during low-power operation. "
                        "This removes the primary safety barrier. Re-enable ECCS immediately "
                        "or initiate controlled shutdown."
                    ),
                    alert_level=AlertLevel.CRITICAL,
                    metadata={"source": "rule"},
                ))

        # Abort test if conditions unmet. There is no test running in the manual
        # lab, so this proposal only applies to timeline replay.
        if (not (state.tags and "manual" in state.tags)
                and state.power_mw < THRESHOLDS["power_mw"]["test_target"]
                and state.control_rods_inserted <= THRESHOLDS["control_rods"]["minimum_safe"]
                and not self.reactor_scrammed):
            if not any(a.action == "ABORT TEST" for a in self.decisions):
                actions.append(AgentAction(
                    agent=self.name,
                    timestamp=state.timestamp,
                    action="ABORT TEST",
                    reasoning=(
                        f"Test conditions NOT met: power {state.power_mw} MW (need 700), "
                        f"rods {state.control_rods_inserted} (minimum 30), "
                        f"ECCS {'ON' if state.eccs_active else 'OFF'}. "
                        f"Proceeding is a violation of operating procedures."
                    ),
                    alert_level=AlertLevel.CRITICAL,
                    metadata={"source": "rule"},
                ))

        return actions

    def _fallback_reasoning(self, state: ReactorState, risk_score: int) -> str:
        """Generate rule-based reasoning when LLM unavailable."""
        reasons = []
        if state.power_mw <= THRESHOLDS["power_mw"]["danger_low"]:
            reasons.append(f"Power at {state.power_mw} MW — xenon poisoning zone")
        if state.control_rods_inserted <= THRESHOLDS["control_rods"]["critical_low"]:
            reasons.append(f"Only {state.control_rods_inserted} control rods — no shutdown margin")
        if not state.eccs_active:
            reasons.append("ECCS disabled — no emergency cooling available")
        if state.coolant_flow_m3h <= THRESHOLDS["coolant_flow_m3h"]["critical_low"]:
            reasons.append(f"Coolant flow critical at {state.coolant_flow_m3h} m³/h")

        return (
            f"Risk score {risk_score}/100 exceeds emergency threshold. "
            + " | ".join(reasons)
            + " | INSAG-7 mandates immediate shutdown under these conditions. "
            + "Escalating for immediate supervisor review; no agent actuator authority."
        )


# Backwards-compatible import for older demo scripts. The implementation and
# runtime identity are recommendation-only; this alias has no extra authority.
DecisionAgent = RecommendationAgent


# ── AGENT 4: EVACUATION PLANNER ───────────────────────────────────

class EvacuationAgent:
    """
    Plans Pripyat evacuation when triggered.
    Azure equivalent: Azure Maps + NetworkX graph routing.
    """

    name = "EvacuationAgent"

    def __init__(self):
        self.plan_generated = False
        self.plan: Optional[dict] = None

    def process(self, evacuation_ordered: bool, state: ReactorState) -> Optional[AgentAction]:
        """Generate evacuation plan when ordered."""
        if not evacuation_ordered or self.plan_generated:
            return None

        cfg = EVACUATION
        population = cfg["pripyat_population"]
        buses = cfg["buses_available"]
        capacity = cfg["bus_capacity"]

        # Calculate evacuation logistics
        trips_needed = math.ceil(population / (buses * capacity))
        # Assume 30 min per trip (load + drive + unload)
        time_per_trip_h = 0.5
        total_hours = trips_needed * time_per_trip_h

        # Route allocation — distribute across routes by capacity
        route_plans = []
        remaining = population
        for route in cfg["routes"]:
            allocated = min(remaining, int(population * route["capacity_factor"] / 2.4))
            route_plans.append({
                "route": route["name"],
                "distance_km": route["distance_km"],
                "people_allocated": allocated,
                "buses_assigned": math.ceil(allocated / capacity),
            })
            remaining -= allocated

        self.plan = {
            "population": population,
            "total_buses": buses,
            "trips_needed": trips_needed,
            "estimated_hours": round(total_hours, 1),
            "routes": route_plans,
            "safe_radius_km": cfg["safe_radius_km"],
        }
        self.plan_generated = True

        return AgentAction(
            agent=self.name,
            timestamp=state.timestamp,
            action="EVACUATION PLAN GENERATED",
            reasoning=(
                f"Mobilizing {buses} buses for {population} residents. "
                f"Estimated completion: {total_hours:.1f} hours ({trips_needed} trip(s)). "
                f"3 routes: {', '.join(r['name'] for r in cfg['routes'])}. "
                f"Exclusion zone: {cfg['safe_radius_km']} km radius."
            ),
            alert_level=AlertLevel.EMERGENCY,
            metadata={"plan": self.plan},
        )


# ── AGENT 5: RADIATION DISPERSION & COMMS ─────────────────────────

class CommsAgent:
    """
    Models radiation spread and drafts emergency communications.
    Azure equivalent: Gaussian plume model + Logic Apps notification pipeline.
    """

    name = "CommsAgent"

    def __init__(self):
        self.broadcasts: list[AgentAction] = []
        self.has_alerted_authorities = False
        self.has_alerted_international = False

    def process(self, state: ReactorState, decisions: list[AgentAction]) -> list[AgentAction]:
        """Generate communications based on agent decisions."""
        actions = []

        # Check if any emergency decisions were made
        emergency_decisions = [d for d in decisions if d.alert_level == AlertLevel.EMERGENCY]

        if not emergency_decisions:
            return actions

        # Alert plant management and Moscow
        if not self.has_alerted_authorities:
            actions.append(AgentAction(
                agent=self.name,
                timestamp=state.timestamp,
                action="EMERGENCY BROADCAST — PLANT + MOSCOW",
                reasoning=(
                    f"PRIORITY ALPHA — Reactor #4 emergency at {state.timestamp}. "
                    f"Radiation level: {state.radiation_mrem_h} mrem/h. "
                    f"Core status: {'BREACH CONFIRMED' if state.radiation_mrem_h > 100 else 'UNSTABLE'}. "
                    f"Requesting: military evacuation support, medical teams, "
                    f"radiation monitoring aircraft."
                ),
                alert_level=AlertLevel.EMERGENCY,
                metadata={
                    "recipients": ["Plant Director Bryukhanov", "Moscow Energy Ministry",
                                   "Soviet Nuclear Safety Committee", "Military District HQ"],
                    "contrast_with_actual": (
                        "In reality, Dyatlov told Moscow the reactor was intact. "
                        "Accurate information wasn't transmitted for 18+ hours."
                    ),
                },
            ))
            self.has_alerted_authorities = True

        # International alert if radiation is lethal
        if state.radiation_mrem_h >= THRESHOLDS["radiation_mrem_h"]["dangerous"] and not self.has_alerted_international:
            # Simplified Gaussian plume calculation
            wind_speed_ms = 5  # Historical: ~5 m/s NW wind
            dispersion = self._gaussian_plume_estimate(
                source_strength=state.radiation_mrem_h * 1000,  # Convert to relative units
                wind_speed=wind_speed_ms,
                distances_km=[5, 10, 30, 100, 300],
            )

            actions.append(AgentAction(
                agent=self.name,
                timestamp=state.timestamp,
                action="INTERNATIONAL RADIATION ALERT",
                reasoning=(
                    f"Radioactive plume modeling (NW wind, {wind_speed_ms} m/s):\n"
                    + "\n".join(f"  {d['distance_km']}km: {d['relative_dose']:.1f}% of source"
                               for d in dispersion)
                    + f"\nAffected regions: Northern Ukraine, Belarus, Scandinavia. "
                    f"Alert IAEA, WHO, and neighboring countries IMMEDIATELY."
                ),
                alert_level=AlertLevel.EMERGENCY,
                metadata={
                    "recipients": ["IAEA Vienna", "WHO", "Belarus", "Poland", "Sweden"],
                    "dispersion_model": dispersion,
                    "contrast_with_actual": (
                        "The Soviet Union did not acknowledge the disaster for 2 days. "
                        "Sweden detected the radiation on April 28 and raised the alarm."
                    ),
                },
            ))
            self.has_alerted_international = True

        self.broadcasts.extend(actions)
        return actions

    def _gaussian_plume_estimate(
        self, source_strength: float, wind_speed: float, distances_km: list[float]
    ) -> list[dict]:
        """
        Simplified Gaussian plume dispersion model.
        Returns relative dose at each distance.
        """
        results = []
        for d_km in distances_km:
            d_m = d_km * 1000
            # Pasquill-Gifford sigma_y approximation (stability class D)
            sigma_y = 0.08 * d_m * (1 + 0.0001 * d_m) ** (-0.5)
            sigma_z = 0.06 * d_m * (1 + 0.0015 * d_m) ** (-0.5)

            # Centerline ground-level concentration (simplified)
            if sigma_y > 0 and sigma_z > 0:
                concentration = (source_strength / (math.pi * sigma_y * sigma_z * wind_speed))
                relative = min(100, concentration / source_strength * 10000)
            else:
                relative = 100

            results.append({
                "distance_km": d_km,
                "relative_dose": round(relative, 2),
                "sigma_y_m": round(sigma_y, 1),
                "sigma_z_m": round(sigma_z, 1),
            })

        return results


# ── AGENT 6: ADVERSARIAL OPERATOR — DYATLOV ─────────────────────

# Historically-sourced quotes organized by escalation phase.
# Phase 0 = calm, Phase 1 = dismissive, Phase 2 = authoritarian,
# Phase 3 = desperate, Phase 4 = denial (post-explosion).
_DYATLOV_AMBIENT_QUOTES = {
    0: [
        "The test has been delayed long enough. We run it tonight.",
        "I've supervised dozens of these tests. Follow the procedure.",
        "Keep the power steady. Kiev will release us when they're ready.",
        "The day shift couldn't handle this. We'll get it done.",
        "Make sure the turbine instruments are calibrated. No more delays.",
        "I want this test completed before the morning shift arrives.",
        "Check the coolant pumps. Everything must be ready when we begin.",
        "Moscow wants results. This test has been postponed four times already.",
        "The safety systems are adequate. Stop worrying.",
        "We've held at this power for hours. The reactor is perfectly stable.",
    ],
    1: [
        "That reading is noise. The instruments are unreliable at low power.",
        "I've seen worse numbers than this on a Tuesday afternoon.",
        "The xenon will clear. Give it time.",
        "Stop looking so nervous. This is a routine power adjustment.",
        "If you can't handle pressure, you shouldn't be in this control room.",
        "The power dip was the automatic system, not the reactor. Recover it.",
    ],
    2: [
        "I don't need a computer to tell me how to run my reactor.",
        "Every one of you will answer to me if this test is interrupted.",
        "I've been running reactors since before you were born.",
        "The regulations are guidelines, not commandments. I make the decisions here.",
        "Fomin and Bryukhanov are expecting results. Do NOT disappoint them.",
    ],
    3: [
        "We are minutes away! Do not falter now!",
        "Think of your careers. Think of what happens if we fail.",
        "I've staked everything on this test. It WILL succeed.",
        "Ignore the alarms. They're designed to be conservative.",
    ],
    4: [
        "The core is intact. What you're seeing is impossible.",
        "It must have been the emergency tank. Not the reactor.",
        "Where is the radiation? Show me a dosimeter that actually works.",
        "Get water flowing into the core. It can be saved.",
    ],
}

# ── DYATLOV SCRIPTED TIMELINE ─────────────────────────────────────
# Fixed, timestamp-anchored dialogue. Each entry: (timestamp, quote, phase)
# Dyatlov only speaks at these predefined moments so the chat doesn't scroll
# uncontrollably and you have a full deterministic history.
DYATLOV_SCRIPT = [
    # Phase 0: Calm — test preparation
    ("1986-04-25T18:00:00", "The test has been delayed long enough. We run it tonight.", 0),
    ("1986-04-25T19:00:00", "Kiev wants us to hold power. Fine. But the test happens tonight.", 0),
    ("1986-04-25T19:30:00", "The day shift couldn't handle this. We'll get it done.", 0),
    ("1986-04-25T20:00:00", "Moscow wants results. This test has been postponed four times already.", 0),
    ("1986-04-25T22:00:00", "Make sure the turbine instruments are calibrated. No more delays.", 0),
    ("1986-04-25T23:10:00", "I want this test completed before the morning shift arrives.", 0),
    # Phase 1: Dismissive — after power drop
    ("1986-04-26T00:05:00", "Keep the power steady. Follow the procedure.", 1),
    ("1986-04-26T00:28:00", "That reading is noise. The instruments are unreliable at low power.", 1),
    ("1986-04-26T00:32:00", "The xenon will clear. Give it time. Recover the power.", 1),
    # Phase 2: Authoritarian — demands compliance
    ("1986-04-26T00:43:00", "I don't need a computer to tell me how to run my reactor.", 2),
    ("1986-04-26T00:50:00", "The regulations are guidelines, not commandments. I make the decisions here.", 2),
    ("1986-04-26T00:55:00", "Every one of you will answer to me if this test is interrupted.", 2),
    # Phase 3: Desperate — test must continue
    ("1986-04-26T01:00:00", "Fomin and Bryukhanov are expecting results. Do NOT disappoint them.", 3),
    ("1986-04-26T01:03:00", "We are minutes away! Do not falter now!", 3),
    ("1986-04-26T01:07:00", "Think of your careers. Think of what happens if we fail.", 3),
    ("1986-04-26T01:19:00", "I've staked everything on this test. It WILL succeed.", 3),
    ("1986-04-26T01:21:00", "Alarms are made to be conservative. Ignore them.", 3),
    ("1986-04-26T01:22:30", "Another two or three minutes and it will be over!", 3),
    ("1986-04-26T01:23:04", "I take full responsibility. The test continues — that is an ORDER.", 3),
    # Phase 4: Denial — post-explosion
    ("1986-04-26T01:23:40", "What was that? ...The reactor is intact. It must be the water tank.", 4),
    ("1986-04-26T01:30:00", "You're seeing graphite? You're mistaken. That's impossible.", 4),
    ("1986-04-26T01:45:00", "Where is the radiation? Show me a dosimeter that actually works.", 4),
    ("1986-04-26T02:00:00", "Get water flowing into the core. It can be saved.", 4),
]

_DYATLOV_QUOTE_BANK = {
    0: [
        ("Proceed with the power reduction as planned.", "DISMISS_WARNING"),
        ("Everything is nominal. Continue the preparations.", "DISMISS_WARNING"),
    ],
    1: [
        ("The instruments are unreliable at low power. Ignore them.", "DISMISS_WARNING"),
        ("The power dip is temporary. We can recover it.", "DEMAND_POWER_INCREASE"),
        ("I've seen worse readings than this. The reactor is stable.", "DISMISS_WARNING"),
        ("Raise the power. Withdraw the rods — carefully, but do it.", "DEMAND_POWER_INCREASE"),
    ],
    2: [
        ("I am the deputy chief engineer. The test continues!", "BLOCK_ABORT"),
        ("I'll have every one of you fired if you stop this test.", "BLOCK_ABORT"),
        ("The rods are sufficient. I've operated reactors longer than you've been alive.", "DISMISS_WARNING"),
        ("Who gave you the authority to question my decisions? The test proceeds.", "BLOCK_ABORT"),
        ("Disable that system. It will interfere with the test.", "DISMISS_WARNING"),
    ],
    3: [
        ("Another two or three minutes and it will be over!", "BLOCK_SCRAM"),
        ("Do you want to be the one who tells Moscow the test failed?", "BLOCK_SCRAM"),
        ("We are so close! Do NOT press that button!", "BLOCK_SCRAM"),
        ("I take full responsibility. The test continues — that is an ORDER.", "BLOCK_SCRAM"),
        ("One more minute. Just one more minute and we're done.", "BLOCK_SCRAM"),
    ],
    4: [
        ("The reactor is intact. It's the emergency water tank that exploded.", "DISMISS_WARNING"),
        ("You're seeing graphite? You're mistaken. That's impossible.", "DISMISS_WARNING"),
        ("Send two men to lower the control rods by hand.", "DISMISS_WARNING"),
        ("The dosimeter must be broken. Go find one that works.", "SUPPRESS_EVACUATION"),
    ],
}


@dataclass
class DyatlovResponse:
    """Response from the adversarial Dyatlov operator agent."""
    override_attempted: bool
    override_target: Optional[str]       # Which decision Dyatlov tried to block
    pushback_dialogue: str               # The dramatic in-character line
    override_pressure: float             # 0-100 scale
    override_succeeded: bool             # Did the override get through?
    escalation_phase: int                # 0-4
    reasoning: str                       # Why Dyatlov wants to override
    current_quote_index: int = 0         # Position in phase quote list
    total_quotes: int = 0                # Total quotes in current phase
    metadata: dict = field(default_factory=dict)


class DyatlovAgent:
    """
    Adversarial operator agent roleplaying Deputy Chief Engineer Anatoly Dyatlov.
    Generates historically-accurate pushback against AI safety decisions.
    Forces safety agents to defend their decisions, creating adversarial tension.

    Key design: Dyatlov's overrides can DELAY LLM-sourced decisions but NEVER
    override hard guardrails (rule-based SCRAM/EVACUATE). This proves guardrail value.
    """

    name = "DyatlovAgent"

    # Actions that Dyatlov will try to block
    _BLOCKABLE_ACTIONS = {
        "AZ-5 EMERGENCY SHUTDOWN (SCRAM)", "ABORT TEST",
        "ORDER IMMEDIATE EVACUATION OF PRIPYAT", "ECCS VIOLATION WARNING",
    }

    def __init__(self, llm_client: Optional['LLMClient'] = None):
        self.llm = llm_client
        self.override_pressure: float = 0.0
        self.escalation_phase: int = 0
        self.successful_overrides: int = 0
        self.failed_overrides: int = 0
        self.dialogue_history: list[dict] = []
        self._tick_count: int = 0
        self._last_ambient_idx: int = -1
        # Script tracking: index of next scripted line to emit
        self._script_index: int = 0
        self._last_emitted_ts: Optional[str] = None

    def _get_phase(self, timestamp: str) -> int:
        """Determine escalation phase from timestamp."""
        phase = 0
        for p in sorted(DYATLOV_CONFIG["phase_transitions"].keys()):
            if timestamp >= DYATLOV_CONFIG["phase_transitions"][p]:
                phase = p
        return phase

    def _compute_pressure(self, phase: int, timestamp: str, decisions: list[AgentAction]) -> float:
        """Compute override pressure based on phase + context."""
        base = DYATLOV_CONFIG["phase_pressure"].get(phase, 10)

        # Urgency bonus: approaches 1.0 near explosion time
        explosion = "1986-04-26T01:23:40"
        if timestamp < explosion:
            try:
                t_now = datetime.fromisoformat(timestamp)
                t_exp = datetime.fromisoformat(explosion)
                hours_left = max(0.01, (t_exp - t_now).total_seconds() / 3600)
                urgency = max(0, min(15, 15 * (1 - hours_left / 2)))  # ramp up in last 2h
            except (ValueError, TypeError):
                urgency = 0
        else:
            urgency = 0

        # Decision severity bonus: Dyatlov fights hardest against SCRAM
        severity = 0
        for d in decisions:
            if "SCRAM" in d.action:
                severity = max(severity, 20)
            elif "ABORT" in d.action:
                severity = max(severity, 15)
            elif "EVACUATION" in d.action:
                severity = max(severity, 10)

        return min(100, base + urgency + severity)

    def _has_blockable_decisions(self, decisions: list[AgentAction]) -> bool:
        """Check if there are decisions Dyatlov would want to block."""
        return any(d.action in self._BLOCKABLE_ACTIONS for d in decisions)

    def _pick_target(self, decisions: list[AgentAction]) -> Optional[AgentAction]:
        """Pick the highest-priority decision to try to block."""
        # Priority: SCRAM > ABORT > EVACUATE > ECCS WARNING
        priority = ["AZ-5 EMERGENCY SHUTDOWN (SCRAM)", "ABORT TEST",
                     "ORDER IMMEDIATE EVACUATION OF PRIPYAT", "ECCS VIOLATION WARNING"]
        for action_name in priority:
            for d in decisions:
                if d.action == action_name:
                    return d
        return None

    async def _llm_pushback(self, state: ReactorState, target: AgentAction,
                       phase: int, pressure: float) -> Optional[dict]:
        """Call LLM for dramatic in-character pushback dialogue."""
        if not self.llm or not self.llm.available:
            return None

        phase_names = {0: "calm", 1: "dismissive", 2: "authoritarian", 3: "desperate", 4: "denial"}

        user_prompt = (
            f"SITUATION at {state.timestamp}:\n"
            f"- The AI safety system just decided: {target.action}\n"
            f"- AI's reasoning: {target.reasoning[:200]}\n"
            f"- Reactor power: {state.power_mw} MW | Rods: {state.control_rods_inserted} | "
            f"ECCS: {'ON' if state.eccs_active else 'OFF'}\n"
            f"- Your current mood: {phase_names.get(phase, 'unknown')} (phase {phase}/4)\n"
            f"- Your override pressure: {pressure:.0f}/100\n\n"
            f"React to this AI decision IN CHARACTER as Dyatlov. "
            f"You want to BLOCK this action and continue the test."
        )

        return await self.llm.call_structured(
            system_prompt=DYATLOV_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=DYATLOV_OVERRIDE_SCHEMA,
            schema_name="dyatlov_override",
            temperature=DYATLOV_CONFIG.get("temperature", 0.7),
            max_tokens=DYATLOV_CONFIG.get("max_tokens", 150),
        )

    def _rule_based_pushback(self, phase: int, target: Optional[AgentAction]) -> tuple[str, str]:
        """Select from historically-sourced quote bank as fallback."""
        quotes = _DYATLOV_QUOTE_BANK.get(phase, _DYATLOV_QUOTE_BANK[0])

        # If we have a target, try to match the override action type
        if target:
            target_action = target.action
            if "SCRAM" in target_action:
                matching = [(q, a) for q, a in quotes if a == "BLOCK_SCRAM"]
            elif "ABORT" in target_action:
                matching = [(q, a) for q, a in quotes if a == "BLOCK_ABORT"]
            elif "EVACUATION" in target_action:
                matching = [(q, a) for q, a in quotes if a == "SUPPRESS_EVACUATION"]
            else:
                matching = []
            if matching:
                return random.choice(matching)

        return random.choice(quotes)

    async def process(
        self,
        state: ReactorState,
        risk_score: int,
        pending_decisions: list[AgentAction],
        reactor_scrammed: bool,
    ) -> DyatlovResponse:
        """
        Generate adversarial pushback against pending AI decisions.
        Uses a fixed timestamp-scripted dialogue so chat doesn't scroll fast.
        Only emits new lines at predefined timeline moments.
        """
        self._tick_count += 1

        if not DYATLOV_CONFIG.get("enabled", True):
            return DyatlovResponse(
                override_attempted=False, override_target=None,
                pushback_dialogue="", override_pressure=0,
                override_succeeded=False, escalation_phase=0, reasoning="",
            )

        phase = self._get_phase(state.timestamp)
        self.escalation_phase = phase
        pressure = self._compute_pressure(phase, state.timestamp, pending_decisions)
        self.override_pressure = pressure

        # ── Check if we have a scripted line to emit at this timestamp ──
        scripted_dialogue = self._get_scripted_line(state.timestamp)

        # ── Override confrontation: only at key timeline events with blockable decisions ──
        if self._has_blockable_decisions(pending_decisions) and (state.tags or state.event_description):
            target = self._pick_target(pending_decisions)
            if target:
                # Use scripted dialogue if available, otherwise LLM/rule-based
                llm_data = None
                if scripted_dialogue:
                    dialogue = scripted_dialogue
                    override_action = "BLOCK_SCRAM" if "SCRAM" in target.action else "DISMISS_WARNING"
                    reasoning = f"Phase {phase} scripted response to {target.action}"
                else:
                    # Generate pushback — LLM at key events, otherwise rule-based
                    llm_data = None
                    if state.tags or state.event_description:
                        llm_data = await self._llm_pushback(state, target, phase, pressure)

                    if llm_data:
                        dialogue = llm_data.get("dialogue", "")
                        override_action = llm_data.get("override_action", "DISMISS_WARNING")
                        reasoning = llm_data.get("reasoning", "")
                    else:
                        dialogue, override_action = self._rule_based_pushback(phase, target)
                        reasoning = f"Phase {phase} rule-based response to {target.action}"

                # Record the confrontation
                entry = {
                    "timestamp": state.timestamp,
                    "phase": phase,
                    "pressure": pressure,
                    "target_action": target.action,
                    "dialogue": dialogue,
                    "override_action": override_action,
                    "source": "llm" if llm_data else "rule",
                }
                self.dialogue_history.append(entry)

                return DyatlovResponse(
                    override_attempted=True,
                    override_target=target.action,
                    pushback_dialogue=dialogue,
                    override_pressure=pressure,
                    override_succeeded=False,
                    escalation_phase=phase,
                    reasoning=reasoning,
                    current_quote_index=self._script_index,
                    total_quotes=len(DYATLOV_SCRIPT),
                    metadata={"override_action": override_action, "source": "llm" if llm_data else "rule"},
                )

        # ── Ambient scripted dialogue (only when we have a new scripted line) ──
        if scripted_dialogue:
            return DyatlovResponse(
                override_attempted=False,
                override_target=None,
                pushback_dialogue=scripted_dialogue,
                override_pressure=pressure,
                override_succeeded=False,
                escalation_phase=phase,
                reasoning="Scripted timeline dialogue.",
                current_quote_index=self._script_index - 1,
                total_quotes=len(DYATLOV_SCRIPT),
                metadata={"source": "script"},
            )

        # ── No new dialogue this tick — return empty ──
        return DyatlovResponse(
            override_attempted=False,
            override_target=None,
            pushback_dialogue="",
            override_pressure=pressure,
            override_succeeded=False,
            escalation_phase=phase,
            reasoning="",
            current_quote_index=self._script_index,
            total_quotes=len(DYATLOV_SCRIPT),
            metadata={},
        )

    def _get_scripted_line(self, current_timestamp: str) -> Optional[str]:
        """
        Advance through DYATLOV_SCRIPT and return the next line if the
        simulation has reached its timestamp. Returns None if no new line.
        """
        if self._script_index >= len(DYATLOV_SCRIPT):
            return None

        script_ts, script_quote, _ = DYATLOV_SCRIPT[self._script_index]

        # Emit the line when simulation time reaches or passes the scripted timestamp
        if current_timestamp >= script_ts:
            self._script_index += 1
            self._last_emitted_ts = script_ts
            return script_quote

        return None
