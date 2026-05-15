"""
PRIPYAT-1986 Agent Orchestrator
In-memory message bus + agent coordination pipeline.

Azure Migration:
- Replace MessageBus with Azure Event Hubs / Service Bus
- Replace state dict with Azure Cosmos DB
- Replace agent pipeline with Azure AI Foundry orchestration
"""

import json
import os
from datetime import datetime
from dataclasses import asdict
from typing import Optional

from config import OUTPUT_DIR, STATE_FILE, DYATLOV_CONFIG
from timeline_data import ReactorState, AI_COUNTERFACTUAL_DECISIONS
from agents import (
    SensorAgent, RiskAgent, DecisionAgent, EvacuationAgent, CommsAgent,
    DyatlovAgent, DyatlovResponse,
    AgentMessage, AgentAction, AlertLevel,
)
from llm_client import LLMClient
from cosmos_logger import CosmosLogger
from audit_logger import AuditLogger


class MessageBus:
    """
    Simple in-memory pub/sub message bus.
    Azure equivalent: Azure Event Hubs with consumer groups.
    """

    def __init__(self):
        self.messages: list[AgentMessage] = []
        self.actions: list[AgentAction] = []

    def publish(self, msg: AgentMessage):
        self.messages.append(msg)

    def publish_action(self, action: AgentAction):
        self.actions.append(action)

    def get_messages_for(self, target: str) -> list[AgentMessage]:
        return [m for m in self.messages if m.target == target or m.target == "broadcast"]

    def clear_tick(self):
        """Clear per-tick messages (keep actions for history)."""
        self.messages.clear()


class Orchestrator:
    """
    Coordinates all agents in a pipeline for each simulation tick.

    Flow per tick:
    1. Simulator emits ReactorState
    2. SensorAgent checks thresholds → alerts
    3. RiskAgent scores risk → escalation
    4. DecisionAgent decides shutdown/evacuate
    5. EvacuationAgent plans if ordered
    6. CommsAgent broadcasts alerts

    State is accumulated and can be serialized for dashboard/audit.
    """

    def __init__(self):
        self.bus = MessageBus()
        self.audit = AuditLogger()  # Audit trail for dashboard log panel
        self.llm = LLMClient(audit=self.audit)  # Shared LLM client for AI-powered agents
        self.cosmos=CosmosLogger()  # Optional Cosmos DB logger for decisions
        self.sensor = SensorAgent()
        self.risk = RiskAgent(llm_client=self.llm)
        self.decision = DecisionAgent(llm_client=self.llm)
        self.dyatlov = DyatlovAgent(llm_client=self.llm)
        self.evacuation = EvacuationAgent()
        self.comms = CommsAgent()

        # Accumulated state for dashboard
        self.tick_count = 0
        self.history: list[dict] = []
        self.all_actions: list[AgentAction] = []
        self.reactor_scrammed = False
        self.evacuation_ordered = False
        self.scram_timestamp: Optional[str] = None
        self.evacuation_timestamp: Optional[str] = None

        # Dyatlov override tracking
        self._delayed_decisions: list[tuple[int, AgentAction]] = []  # (reinject_at_tick, action)
        self.override_history: list[dict] = []
        self.total_override_attempts: int = 0
        self.total_override_failures: int = 0
        self.total_override_delays: int = 0

        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def _resolve_overrides(
        self, decisions: list[AgentAction], dyatlov: DyatlovResponse
    ) -> list[AgentAction]:
        """
        Resolve Dyatlov's override attempts against pending decisions.
        Guardrail (rule-sourced) decisions can NEVER be overridden.
        LLM-sourced non-SCRAM decisions can be temporarily DELAYED in early phases.
        """
        if not dyatlov.override_attempted:
            return decisions

        self.total_override_attempts += 1
        final = []

        for d in decisions:
            source = d.metadata.get("source", "rule")

            # Guardrail decisions: NEVER overridable
            if source == "rule":
                final.append(d)
                dyatlov.override_succeeded = False
                self.total_override_failures += 1
                continue

            # LLM decisions: can be delayed in early phases for non-SCRAM actions
            if (source == "llm"
                    and dyatlov.override_pressure > 50
                    and "SCRAM" not in d.action
                    and "EVACUATION" not in d.action
                    and dyatlov.escalation_phase <= 2):
                # Override succeeds temporarily — decision delayed
                delay_ticks = min(
                    DYATLOV_CONFIG.get("max_delay_ticks", 3),
                    2 if dyatlov.escalation_phase == 1 else 3,
                )
                self._delayed_decisions.append((self.tick_count + delay_ticks, d))
                dyatlov.override_succeeded = True
                self.total_override_delays += 1
            else:
                final.append(d)
                dyatlov.override_succeeded = False
                self.total_override_failures += 1

        # Record this confrontation
        self.override_history.append({
            "tick": self.tick_count,
            "timestamp": dyatlov.metadata.get("timestamp", ""),
            "phase": dyatlov.escalation_phase,
            "pressure": dyatlov.override_pressure,
            "target": dyatlov.override_target,
            "dialogue": dyatlov.pushback_dialogue,
            "succeeded": dyatlov.override_succeeded,
        })

        return final

    def _reinject_delayed_decisions(self) -> list[AgentAction]:
        """Re-inject decisions that Dyatlov delayed once their delay expires."""
        ready = [action for tick, action in self._delayed_decisions if tick <= self.tick_count]
        self._delayed_decisions = [
            (tick, action) for tick, action in self._delayed_decisions if tick > self.tick_count
        ]
        return ready

    async def process_tick(self, state: ReactorState) -> dict:
        """
        Process one simulation tick through the full agent pipeline.
        Returns a summary dict for the dashboard.
        """
        self.tick_count += 1
        self.bus.clear_tick()
        self.audit.set_tick(self.tick_count, state.timestamp)

        # Audit: log tick start with reactor telemetry
        self.audit.log(
            agent="Orchestrator", log_type="TICK_START", direction="INPUT",
            detail=f"Power={state.power_mw:.0f}MW Rods={state.control_rods_inserted} Coolant={state.coolant_flow_m3h:.0f} Temp={state.temperature_c:.0f}°C Rad={state.radiation_mrem_h:.4f}",
            source="physics", status="ok",
            data={"power_mw": state.power_mw, "control_rods": state.control_rods_inserted,
                  "coolant_flow": state.coolant_flow_m3h, "steam_pressure": state.steam_pressure_mpa,
                  "temperature_c": state.temperature_c, "radiation": state.radiation_mrem_h,
                  "eccs_active": state.eccs_active, "event": state.event_description},
        )

        # ── Step 0: Re-inject delayed decisions from previous Dyatlov overrides
        reinjected = self._reinject_delayed_decisions()
        for d in reinjected:
            self.bus.publish_action(d)
            self.all_actions.append(d)
            self.audit.log(
                agent="Orchestrator", log_type="REINJECT", direction="DECISION",
                detail=f"Re-injected delayed decision: {d.action}",
                source=d.metadata.get("source", "rule"), status="ok",
                data={"action": d.action, "reasoning": d.reasoning},
            )

        # ── Step 1: Sensor Agent ──────────────────────────────────
        sensor_alerts = self.sensor.process(state)
        for alert in sensor_alerts:
            self.bus.publish(alert)
        if sensor_alerts:
            for alert in sensor_alerts:
                self.audit.log(
                    agent="SensorAgent", log_type="SENSOR_ALERT", direction="OUTPUT",
                    detail=f"[{alert.alert_level.value}] {alert.msg_type}: {alert.payload.get('detail', '')[:150]}",
                    source="rule", status="ok",
                    data={"msg_type": alert.msg_type, "level": alert.alert_level.value, "payload": alert.payload},
                )
        else:
            self.audit.log(
                agent="SensorAgent", log_type="SENSOR_CHECK", direction="OUTPUT",
                detail="All parameters within thresholds",
                source="rule", status="ok",
            )

        # ── Step 2: Risk Agent ────────────────────────────────────
        risk_score, risk_msg = await self.risk.process(state, sensor_alerts)
        self.bus.publish(risk_msg)
        risk_source = risk_msg.payload.get("source", "rule")
        self.audit.log(
            agent="RiskAgent", log_type="RISK_CALC", direction="OUTPUT",
            detail=f"Risk={risk_score}/100 [{risk_msg.alert_level.value}] source={risk_source}"
                   + (f" | AI: {risk_msg.payload.get('ai_reasoning', '')[:120]}" if risk_source == "llm" else ""),
            source=risk_source, status="ok",
            data={"risk_score": risk_score, "rule_score": risk_msg.payload.get("rule_score"),
                  "component_scores": risk_msg.payload.get("component_scores"),
                  "level": risk_msg.alert_level.value, "source": risk_source,
                  "ai_reasoning": risk_msg.payload.get("ai_reasoning")},
        )

        # ── Step 3: Decision Agent ────────────────────────────────
        decisions = await self.decision.process(state, risk_score, sensor_alerts)
        for d in decisions:
            self.audit.log(
                agent="DecisionAgent", log_type="DECISION", direction="DECISION",
                detail=f"[{d.alert_level.value}] {d.action} (source={d.metadata.get('source','rule')}): {d.reasoning[:150]}",
                source=d.metadata.get("source", "rule"), status="ok",
                data={"action": d.action, "reasoning": d.reasoning, "level": d.alert_level.value,
                      "source": d.metadata.get("source", "rule")},
            )
        if not decisions:
            if self.reactor_scrammed or self.evacuation_ordered:
                detail = f"Monitoring continues — prior actions in effect (risk={risk_score})"
            else:
                detail = f"No action required (risk={risk_score})"
            self.audit.log(
                agent="DecisionAgent", log_type="DECISION", direction="OUTPUT",
                detail=detail,
                source="rule", status="ok",
            )

        # ── Step 3.5: Dyatlov Adversarial Agent ───────────────────
        # Skip Dyatlov in manual mode — operator IS the human
        if "manual" in (state.tags or []):
            dyatlov_response = DyatlovResponse(
                override_attempted=False, override_target=None,
                pushback_dialogue="", override_pressure=0,
                override_succeeded=False, escalation_phase=0, reasoning="",
            )
        else:
            dyatlov_response = await self.dyatlov.process(
                state, risk_score, decisions, self.reactor_scrammed,
            )
            if dyatlov_response.override_attempted:
                self.audit.log(
                    agent="DyatlovAgent", log_type="OVERRIDE", direction="DECISION",
                    detail=f"Override attempt (phase={dyatlov_response.escalation_phase}, pressure={dyatlov_response.override_pressure}%): \"{dyatlov_response.pushback_dialogue[:120]}\"",
                    source="llm" if dyatlov_response.pushback_dialogue else "rule",
                    status="delayed" if dyatlov_response.override_succeeded else "blocked",
                    data={"phase": dyatlov_response.escalation_phase, "pressure": dyatlov_response.override_pressure,
                          "target": dyatlov_response.override_target, "succeeded": dyatlov_response.override_succeeded,
                          "dialogue": dyatlov_response.pushback_dialogue},
                )

        # ── Step 3.6: Override Resolution ─────────────────────────
        pre_override_count = len(decisions)
        decisions = self._resolve_overrides(decisions, dyatlov_response)
        if pre_override_count != len(decisions):
            self.audit.log(
                agent="Guardrail", log_type="OVERRIDE_RESOLVE", direction="DECISION",
                detail=f"Override resolution: {pre_override_count} decisions → {len(decisions)} after Dyatlov",
                source="rule", status="ok",
                data={"before": pre_override_count, "after": len(decisions)},
            )

        # Include reinjected decisions in this tick's decisions list
        decisions = reinjected + decisions

        for d in decisions:
            if d not in reinjected:  # avoid double-counting reinjected
                self.bus.publish_action(d)
                self.all_actions.append(d)

        # Track state changes
        if self.decision.reactor_scrammed and not self.reactor_scrammed:
            self.reactor_scrammed = True
            self.scram_timestamp = state.timestamp
            self.audit.log(
                agent="Orchestrator", log_type="STATE_CHANGE", direction="DECISION",
                detail=f"REACTOR SCRAMMED at {state.timestamp}",
                source="rule", status="ok",
            )
            self.audit.log(
                agent="Orchestrator", log_type="STATE_CHANGE", direction="OUTPUT",
                detail=(
                    "SCRAM NOTE: AZ-5 activated but RBMK graphite-tipped rod design causes "
                    "initial reactivity surge before shutdown. Historical timeline continues — "
                    "operators withdrew rods attempting power recovery despite SCRAM order."
                ),
                source="rule", status="warning",
            )
        if self.decision.evacuation_ordered and not self.evacuation_ordered:
            self.evacuation_ordered = True
            self.evacuation_timestamp = state.timestamp
            # Signal RiskAgent to stop calling LLM (rules suffice post-evacuation)
            self.risk._evacuation_done = True
            self.audit.log(
                agent="Orchestrator", log_type="STATE_CHANGE", direction="DECISION",
                detail=f"EVACUATION ORDERED at {state.timestamp}",
                source="rule", status="ok",
            )

        # ── Step 4: Evacuation Agent ──────────────────────────────
        evac_action = self.evacuation.process(self.evacuation_ordered, state)
        if evac_action:
            self.bus.publish_action(evac_action)
            self.all_actions.append(evac_action)
            decisions.append(evac_action)
            self.audit.log(
                agent="EvacuationAgent", log_type="EVACUATION", direction="DECISION",
                detail=f"{evac_action.action}: {evac_action.reasoning[:150]}",
                source="rule", status="ok",
                data={"action": evac_action.action, "reasoning": evac_action.reasoning},
            )

        # ── Step 5: Comms Agent ───────────────────────────────────
        comms_actions = self.comms.process(state, decisions)
        for ca in comms_actions:
            self.bus.publish_action(ca)
            self.all_actions.append(ca)
            decisions.append(ca)
            self.audit.log(
                agent="CommsAgent", log_type="COMMS", direction="OUTPUT",
                detail=f"{ca.action}: {ca.reasoning[:150]}",
                source="rule", status="ok",
            )

        # ── Build tick summary ────────────────────────────────────
        counterfactual = AI_COUNTERFACTUAL_DECISIONS.get(state.timestamp)

        summary = {
            "tick": self.tick_count,
            "timestamp": state.timestamp,
            "reactor": {
                "power_mw": state.power_mw,
                "control_rods": state.control_rods_inserted,
                "coolant_flow": state.coolant_flow_m3h,
                "steam_pressure": state.steam_pressure_mpa,
                "temperature_c": state.temperature_c,
                "radiation": state.radiation_mrem_h,
                "eccs_active": state.eccs_active,
            },
            "risk_score": risk_score,
            "alert_level": risk_msg.alert_level.value,
            "sensor_alerts": len(sensor_alerts),
            "decisions": [
                {
                    "agent": d.agent,
                    "action": d.action,
                    "reasoning": d.reasoning,
                    "level": d.alert_level.value,
                    "source": d.metadata.get("source", "rule"),
                }
                for d in decisions
            ],
            "risk_source": risk_msg.payload.get("source", "rule"),
            "risk_ai_reasoning": risk_msg.payload.get("ai_reasoning"),
            "actual_event": state.event_description,
            "actual_decision": state.actual_human_decision,
            "counterfactual": counterfactual,
            "dyatlov": {
                "override_attempted": dyatlov_response.override_attempted,
                "override_target": dyatlov_response.override_target,
                "pushback_dialogue": dyatlov_response.pushback_dialogue,
                "override_pressure": dyatlov_response.override_pressure,
                "override_succeeded": dyatlov_response.override_succeeded,
                "escalation_phase": dyatlov_response.escalation_phase,
                "total_attempts": self.total_override_attempts,
                "total_failures": self.total_override_failures,
                "total_delays": self.total_override_delays,
            },
            "state": {
                "reactor_scrammed": self.reactor_scrammed,
                "scram_time": self.scram_timestamp,
                "evacuation_ordered": self.evacuation_ordered,
                "evacuation_time": self.evacuation_timestamp,
            },
            "llm_stats": self.llm.get_stats(),
            "audit_log": self.audit.drain(),  # Drain per-tick audit entries
        }

        self.history.append(summary)
        # Log decisions to Cosmos DB audit trail
        for d in decisions:
            self.cosmos.log_decision(d.agent, self.tick_count, state.timestamp, {
                "action": d.action, "reasoning": d.reasoning, "source": d.metadata.get("source", "rule")
            })

        return summary

    def reset(self):
        """Reset orchestrator to initial state."""
        self.bus = MessageBus()
        self.audit = AuditLogger()
        self.llm = LLMClient(audit=self.audit)
        self.cosmos=CosmosLogger()
        self.sensor = SensorAgent()
        self.risk = RiskAgent(llm_client=self.llm)
        self.decision = DecisionAgent(llm_client=self.llm)
        self.dyatlov = DyatlovAgent(llm_client=self.llm)
        self.evacuation = EvacuationAgent()
        self.comms = CommsAgent()
        self.tick_count = 0
        self.history.clear()
        self.all_actions.clear()
        self.reactor_scrammed = False
        self.evacuation_ordered = False
        self.scram_timestamp = None
        self.evacuation_timestamp = None
        self._delayed_decisions.clear()
        self.override_history.clear()
        self.total_override_attempts = 0
        self.total_override_failures = 0
        self.total_override_delays = 0

    def get_state_snapshot(self) -> dict:
        """Return serializable state snapshot."""
        return {
            "total_ticks": self.tick_count,
            "reactor_scrammed": self.reactor_scrammed,
            "scram_timestamp": self.scram_timestamp,
            "evacuation_ordered": self.evacuation_ordered,
            "evacuation_timestamp": self.evacuation_timestamp,
            "total_actions": len(self.all_actions),
            "risk_score_history": self.risk.score_history,
        }

    def save_state(self):
        """Persist full state to JSON (Azure: Cosmos DB)."""
        # Flush any remaining dedup summaries before saving
        self.audit.flush_dedup()

        state = {
            "total_ticks": self.tick_count,
            "reactor_scrammed": self.reactor_scrammed,
            "scram_timestamp": self.scram_timestamp,
            "evacuation_ordered": self.evacuation_ordered,
            "evacuation_timestamp": self.evacuation_timestamp,
            "total_actions": len(self.all_actions),
            "risk_score_history": self.risk.score_history,
            "evacuation_plan": self.evacuation.plan,
            "llm_stats": self.llm.get_stats(),
            "actions": [
                {
                    "agent": a.agent,
                    "timestamp": a.timestamp,
                    "action": a.action,
                    "reasoning": a.reasoning,
                    "level": a.alert_level.value,
                    "source": a.metadata.get("source", "rule"),
                }
                for a in self.all_actions
            ],
        }

        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def get_final_report(self) -> dict:
        """Generate final comparison report: actual vs AI."""
        actual_evacuation = "1986-04-27T14:00:00"  # 36 hours after explosion
        actual_deaths_immediate = 31
        actual_deaths_longterm = 4000  # WHO estimate

        ai_evac = self.evacuation_timestamp or "NOT TRIGGERED"
        ai_scram = self.scram_timestamp or "NOT TRIGGERED"

        # Calculate time savings
        time_saved_evac = None
        if self.evacuation_timestamp:
            t_actual = datetime.fromisoformat(actual_evacuation)
            t_ai = datetime.fromisoformat(self.evacuation_timestamp)
            time_saved_evac = (t_actual - t_ai).total_seconds() / 3600  # hours

        # Dyatlov confrontation analysis
        key_confrontations = [
            h for h in self.override_history
            if h.get("pressure", 0) >= 60
        ][-5:]  # Top 5 most intense

        return {
            "title": "PRIPYAT-1986 — Alternate History Report",
            "actual_timeline": {
                "explosion": "1986-04-26T01:23:40",
                "evacuation_ordered": actual_evacuation,
                "evacuation_delay_hours": 36,
                "immediate_deaths": actual_deaths_immediate,
                "estimated_longterm_deaths": actual_deaths_longterm,
            },
            "ai_timeline": {
                "scram_ordered": ai_scram,
                "evacuation_ordered": ai_evac,
                "evacuation_hours_earlier": round(time_saved_evac, 1) if time_saved_evac else None,
                "explosion_prevented": self.reactor_scrammed and (
                    ai_scram < "1986-04-26T01:23:00" if ai_scram != "NOT TRIGGERED" else False
                ),
            },
            "dyatlov_analysis": {
                "total_override_attempts": self.total_override_attempts,
                "overrides_blocked_by_guardrails": self.total_override_failures,
                "overrides_delayed": self.total_override_delays,
                "peak_override_pressure": max(
                    (h.get("pressure", 0) for h in self.override_history), default=0
                ),
                "escalation_phases_reached": self.dyatlov.escalation_phase,
                "key_confrontations": key_confrontations,
            },
            "total_agent_actions": len(self.all_actions),
            "peak_risk_score": max((s for _, s in self.risk.score_history), default=0),
            "evacuation_plan": self.evacuation.plan,
            "llm_stats": self.llm.get_stats(),
        }
