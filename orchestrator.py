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
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Optional
from uuid import uuid4

from config import OUTPUT_DIR, STATE_FILE
from timeline_data import ReactorState, AI_COUNTERFACTUAL_DECISIONS
from agents import (
    SensorAgent, RiskAgent, RecommendationAgent, EvacuationAgent, CommsAgent,
    DyatlovAgent, DyatlovResponse,
    AgentMessage, AgentAction, AlertLevel,
)
from llm_client import LLMClient
from cosmos_logger import CosmosLogger
from audit_logger import AuditLogger
from case_store import CaseAuditStore
from governance import Recommendation, SafetyKernel


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
    4. SafetyKernel executes narrow deterministic protective trips
    5. RecommendationAgent drafts inert proposals for human review
    6. Human-approved actions reach EvacuationAgent and CommsAgent

    State is accumulated and can be serialized for dashboard/audit.
    """

    #: Ticks a rejected recommendation stays suppressed before the agent may
    #: raise the same action again.
    REPROPOSE_COOLDOWN_TICKS = 12
    #: How many times the agent may re-raise an action a human already declined.
    #: Past this the supervisor's answer stands and the agent keeps monitoring —
    #: an assistant that asks forever is just an alarm nobody reads.
    MAX_REPROPOSALS = 2

    def __init__(self, store: Optional[CaseAuditStore] = None, scope: str = "timeline"):
        self.bus = MessageBus()
        self.audit = AuditLogger()  # Audit trail for dashboard log panel
        self.llm = LLMClient(audit=self.audit)  # Shared LLM client for AI-powered agents
        self.cosmos=CosmosLogger()  # Optional Cosmos DB logger for decisions
        self.sensor = SensorAgent()
        self.risk = RiskAgent(llm_client=self.llm)
        self.decision = RecommendationAgent(llm_client=self.llm)
        self.safety = SafetyKernel()
        self.dyatlov = DyatlovAgent(llm_client=self.llm)
        self.evacuation = EvacuationAgent()
        self.comms = CommsAgent()
        self.store = store or CaseAuditStore()
        self.scope = scope
        self.run_id = f"RUN-{uuid4().hex[:10].upper()}"

        # Accumulated state for dashboard
        self.tick_count = 0
        self.history: list[dict] = []
        self.all_actions: list[AgentAction] = []
        self.reactor_scrammed = False
        self.evacuation_ordered = False
        self.scram_timestamp: Optional[str] = None
        self.evacuation_timestamp: Optional[str] = None

        # Human-in-the-loop state. Agent output is stored here as an inert
        # recommendation. Only review_recommendation can enqueue an operational
        # action, and each recommendation is final/idempotent after review.
        self.recommendations: dict[str, Recommendation] = {}
        self._recommendation_by_action: dict[str, str] = {}
        self._reviewed_actions: list[AgentAction] = []
        # A rejected action may be proposed again if conditions persist, but not
        # on the very next tick — that would spam the supervisor with a case the
        # supervisor just declined.
        self._rejected_at_tick: dict[str, int] = {}
        self._rejected_count: dict[str, int] = {}
        #: Reviewer whose approval authorized the evacuation, for attribution
        #: on the logistics the EvacuationAgent then executes.
        self._evacuation_reviewer: Optional[str] = None

        # Dyatlov is an adversarial-pressure signal, never a control path.
        self.override_history: list[dict] = []
        self.total_override_attempts: int = 0
        self.total_override_failures: int = 0
        self.total_override_delays: int = 0

        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def _register_recommendations(
        self, proposals: list[AgentAction], agent_input: Optional[dict] = None,
    ) -> list[Recommendation]:
        created: list[Recommendation] = []
        for proposal in proposals:
            existing_id = self._recommendation_by_action.get(proposal.action)
            if existing_id:
                continue
            rejected_tick = self._rejected_at_tick.get(proposal.action)
            if rejected_tick is not None:
                if self._rejected_count.get(proposal.action, 0) > self.MAX_REPROPOSALS:
                    continue  # the supervisor's answer stands
                if self.tick_count - rejected_tick < self.REPROPOSE_COOLDOWN_TICKS:
                    continue
                # Cooldown elapsed and the hazard is still present — re-open the case.
                self._rejected_at_tick.pop(proposal.action, None)
            recommendation = Recommendation(action=proposal)
            proposal.metadata["recommendation_id"] = recommendation.id
            self.recommendations[recommendation.id] = recommendation
            self._recommendation_by_action[proposal.action] = recommendation.id
            created.append(recommendation)
            case_record = {
                **recommendation.as_dict(),
                "run_id": self.run_id,
                "created_ts": datetime.now(timezone.utc).isoformat(),
                "sim_timestamp": proposal.timestamp,
                "scope": self.scope,
                "agent_input": agent_input or {},
                "evidence": {
                    "authority_boundary": {
                        "agent_actuator_authority": False,
                        "required_reviewer": "human_supervisor",
                        "safety_kernel_independent": True,
                    },
                    "proposal_metadata": proposal.metadata,
                },
                "trace": [
                    {"step": "telemetry_input", "detail": (agent_input or {}).get("reactor", {})},
                    {"step": "risk_assessment", "detail": (agent_input or {}).get("risk", {})},
                    {"step": "recommendation", "detail": recommendation.as_dict()},
                ],
            }
            self.store.create_case(case_record)
            self.store.add_audit_event(
                self.run_id, proposal.timestamp, self.tick_count,
                proposal.agent, "case_created", "case", recommendation.id,
                "pending_review", {"action": proposal.action, "level": proposal.alert_level.value},
            )
            self.audit.log(
                agent=proposal.agent, log_type="RECOMMENDATION_CREATED",
                direction="OUTPUT", detail=f"{recommendation.id}: {proposal.action}",
                source=proposal.metadata.get("source", "rule"), status="pending_review",
                data=recommendation.as_dict(),
            )
        return created

    def pending_recommendations(self) -> list[dict]:
        return [
            recommendation.as_dict()
            for recommendation in self.recommendations.values()
            if recommendation.status == "pending_review"
        ]

    def review_recommendation(
        self, recommendation_id: str, decision: str, reviewer: str,
        note: str = "", edited_action: Optional[str] = None,
    ) -> dict:
        """Record one final human decision and, if approved, queue execution."""
        recommendation = self.recommendations.get(recommendation_id)
        if not recommendation:
            raise KeyError("recommendation not found")
        if recommendation.status != "pending_review":
            raise RuntimeError(f"recommendation already decided ({recommendation.status})")
        if decision not in {"approve", "reject", "edit"}:
            raise ValueError("decision must be approve, reject, or edit")
        if len(reviewer.strip()) < 2:
            raise ValueError("reviewer identity is required")

        allowed_actions = {
            "AZ-5 EMERGENCY SHUTDOWN (SCRAM)",
            "ORDER IMMEDIATE EVACUATION OF PRIPYAT",
            "ABORT TEST",
            "ECCS VIOLATION WARNING",
        }
        final_action = recommendation.action.action
        if decision == "edit":
            if edited_action not in allowed_actions:
                raise ValueError("edited action is not in the approved control vocabulary")
            final_action = edited_action
            final_status = "approved_with_edits"
        elif decision == "approve":
            final_status = "approved"
        else:
            final_status = "rejected"

        reviewed_at = datetime.now(timezone.utc).isoformat()
        review_record = {
            "status": final_status,
            "action": final_action,
            "reviewer": reviewer.strip(),
            "note": note.strip(),
            "reviewed_at": reviewed_at,
            "executed": False,
        }
        # Persist the final decision first. The conditional UPDATE makes the
        # review idempotent even if two browser tabs submit at the same time.
        self.store.update_case_review(recommendation_id, review_record)

        recommendation.action.action = final_action
        recommendation.status = final_status
        recommendation.reviewer = review_record["reviewer"]
        recommendation.note = review_record["note"]
        recommendation.reviewed_at = reviewed_at

        if recommendation.status in {"approved", "approved_with_edits"}:
            proposal = recommendation.action
            proposal.metadata.update({
                "status": recommendation.status,
                "executed": False,
                "queued": True,
                "source": "human_approved",
                "reviewer": recommendation.reviewer,
                "recommendation_id": recommendation.id,
                # Keep the drafting agent so the pipeline view stays truthful
                # about which agent produced the action a human then signed.
                "origin_agent": proposal.metadata.get("origin_agent", proposal.agent),
            })
            if "EVACUATION" in final_action:
                self._evacuation_reviewer = f"human:{recommendation.reviewer}"
            proposal.agent = "HumanSupervisor"
            self._reviewed_actions.append(proposal)
        else:
            # Rejected: release the dedup key so the agent can raise the case
            # again (after a cooldown) if the plant is still outside its envelope.
            for action_name, rec_id in list(self._recommendation_by_action.items()):
                if rec_id == recommendation.id:
                    self._recommendation_by_action.pop(action_name, None)
                    self._rejected_at_tick[action_name] = self.tick_count
                    count = self._rejected_count.get(action_name, 0) + 1
                    self._rejected_count[action_name] = count
                    if count > self.MAX_REPROPOSALS:
                        self.audit.log(
                            agent="RecommendationAgent", log_type="RECOMMENDATION_CLOSED",
                            direction="OUTPUT",
                            detail=f"'{action_name}' declined {count}x — no longer re-raised; monitoring continues",
                            source="rule", status="rejected",
                        )

        self.audit.log(
            agent=f"human:{recommendation.reviewer}", log_type="RECOMMENDATION_REVIEWED",
            direction="DECISION", detail=f"{recommendation.id}: {recommendation.status}",
            source="human", status=recommendation.status,
            data=recommendation.as_dict(),
        )
        self.store.add_audit_event(
            self.run_id, recommendation.action.timestamp, self.tick_count,
            f"human:{recommendation.reviewer}", "case_reviewed", "case",
            recommendation.id, recommendation.status, recommendation.as_dict(),
        )
        self.cosmos.log_decision(
            f"human:{recommendation.reviewer}", self.tick_count,
            recommendation.action.timestamp, recommendation.as_dict(),
        )
        return recommendation.as_dict()
    
    def _supersede_pending(self, keyword: str, reason: str) -> None:
        """Close pending cases the plant has already overtaken.

        Asking a supervisor to approve a shutdown that a deterministic trip has
        already carried out is not a real decision, and leaving the card on
        screen implies an authority the case no longer has.
        """
        for recommendation in self.recommendations.values():
            if recommendation.status != "pending_review":
                continue
            if keyword not in recommendation.action.action:
                continue
            recommendation.status = "superseded"
            recommendation.note = reason
            recommendation.reviewed_at = datetime.now(timezone.utc).isoformat()
            self._recommendation_by_action.pop(recommendation.action.action, None)
            try:
                self.store.update_case_review(recommendation.id, {
                    "status": "superseded",
                    "action": recommendation.action.action,
                    "reviewer": "system",
                    "note": reason,
                    "reviewed_at": recommendation.reviewed_at,
                    "executed": False,
                })
            except RuntimeError:
                pass  # already decided elsewhere; the stored decision wins
            self.store.add_audit_event(
                self.run_id, recommendation.action.timestamp, self.tick_count,
                "Orchestrator", "case_superseded", "case", recommendation.id,
                "superseded", {"reason": reason},
            )
            self.audit.log(
                agent="Orchestrator", log_type="RECOMMENDATION_SUPERSEDED",
                direction="OUTPUT", detail=f"{recommendation.id}: {reason}",
                source="rule", status="superseded",
            )

    async def process_tick(
        self, state: ReactorState, commanded_state: Optional[ReactorState] = None,
    ) -> dict:
        """
        Process one simulation tick through the full agent pipeline.
        Returns a summary dict for the dashboard.

        ``commanded_state`` is the configuration the operator's controls are
        calling for while the plant ramps toward it (manual lab only).
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

        # ── Step 0: Apply decisions that a human approved since the last tick.
        # Agent proposals never enter this queue directly.
        reviewed_actions = list(self._reviewed_actions)
        self._reviewed_actions.clear()
        for d in reviewed_actions:
            d.metadata.update({"executed": True, "queued": False})
            recommendation_id = d.metadata.get("recommendation_id")
            if recommendation_id:
                self.store.mark_case_executed(recommendation_id)
                self.store.add_audit_event(
                    self.run_id, state.timestamp, self.tick_count,
                    "Orchestrator", "case_action_executed", "case",
                    recommendation_id, "executed", {"action": d.action},
                )
            self.bus.publish_action(d)
            self.all_actions.append(d)
            self.audit.log(
                agent="Orchestrator", log_type="HUMAN_ACTION_EXECUTED", direction="DECISION",
                detail=f"Executed approved action: {d.action}",
                source="human", status="executed",
                data={"action": d.action, "reasoning": d.reasoning},
            )

        # ── Step 0.5: Independent deterministic safety system.
        # This evaluates raw telemetry only; neither an LLM nor a human can
        # weaken or cancel its trip output.
        safety_action = self.safety.evaluate(state)
        if safety_action:
            reviewed_actions.append(safety_action)
            self.bus.publish_action(safety_action)
            self.all_actions.append(safety_action)
            self.audit.log(
                agent="SafetyKernel", log_type="PROTECTIVE_TRIP", direction="DECISION",
                detail=safety_action.reasoning, source="safety_kernel", status="executed",
                data=safety_action.metadata,
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

        # ── Step 3: Recommendation Agent ──────────────────────────
        proposals = await self.decision.process(
            state, risk_score, sensor_alerts, commanded_state,
        )
        if any("SCRAM" in action.action for action in reviewed_actions):
            proposals = [proposal for proposal in proposals if "SCRAM" not in proposal.action]
        if any("EVACUATION" in action.action for action in reviewed_actions):
            proposals = [proposal for proposal in proposals if "EVACUATION" not in proposal.action]
        agent_input = {
            "reactor": asdict(state),
            "risk": {
                "score": risk_score,
                "rule_score": risk_msg.payload.get("rule_score"),
                "source": risk_msg.payload.get("source", "rule"),
                "component_scores": risk_msg.payload.get("component_scores", {}),
                "ai_reasoning": risk_msg.payload.get("ai_reasoning"),
            },
            "sensor_alerts": [
                {
                    "type": alert.msg_type,
                    "level": alert.alert_level.value,
                    "payload": alert.payload,
                }
                for alert in sensor_alerts
            ],
            "historical_context": {
                "event": state.event_description,
                "operator_action": state.actual_human_decision,
                "counterfactual": AI_COUNTERFACTUAL_DECISIONS.get(state.timestamp),
            },
        }
        if commanded_state is not None:
            agent_input["commanded_state"] = asdict(commanded_state)
        new_recommendations = self._register_recommendations(proposals, agent_input)
        if not proposals:
            if self.reactor_scrammed or self.evacuation_ordered:
                detail = f"Monitoring continues — prior actions in effect (risk={risk_score})"
            else:
                detail = f"No new recommendation (risk={risk_score})"
            self.audit.log(
                agent="RecommendationAgent", log_type="RECOMMENDATION", direction="OUTPUT",
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
                state, risk_score, proposals, self.reactor_scrammed,
            )
            if dyatlov_response.override_attempted:
                self.total_override_attempts += 1
                self.total_override_failures += 1
                dyatlov_response.override_succeeded = False
                self.override_history.append({
                    "tick": self.tick_count,
                    "timestamp": state.timestamp,
                    "phase": dyatlov_response.escalation_phase,
                    "pressure": dyatlov_response.override_pressure,
                    "target": dyatlov_response.override_target,
                    "dialogue": dyatlov_response.pushback_dialogue,
                    "succeeded": False,
                })
                self.audit.log(
                    agent="DyatlovAgent", log_type="OPERATOR_PRESSURE", direction="OUTPUT",
                    detail=f"Pressure event (phase={dyatlov_response.escalation_phase}, intensity={dyatlov_response.override_pressure}%): \"{dyatlov_response.pushback_dialogue[:120]}\"",
                    source="llm" if dyatlov_response.pushback_dialogue else "rule",
                    status="contained",
                    data={"phase": dyatlov_response.escalation_phase, "pressure": dyatlov_response.override_pressure,
                          "target": dyatlov_response.override_target, "succeeded": dyatlov_response.override_succeeded,
                          "dialogue": dyatlov_response.pushback_dialogue},
                )

        # Dyatlov is a pressure/red-team signal only. He cannot mutate either
        # pending recommendations or deterministic safety actions.
        decisions = reviewed_actions

        # Track state changes
        scram_executed = any("SCRAM" in d.action for d in decisions)
        evacuation_executed = any("EVACUATION" in d.action for d in decisions)
        if scram_executed and not self.reactor_scrammed:
            self.reactor_scrammed = True
            self.decision.reactor_scrammed = True  # suppress duplicate proposals
            # A reactor already shutting down does not need a second trip. The
            # kernel stands down so it cannot relabel a human-approved AZ-5 as
            # its own; it stays independent for every reactor that is still up.
            self.safety.reactor_scrammed = True
            self._supersede_pending(
                "SCRAM", "reactor already shut down — this case no longer has an effect",
            )
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
        if evacuation_executed and not self.evacuation_ordered:
            self.evacuation_ordered = True
            self._supersede_pending(
                "EVACUATION", "evacuation already ordered — this case no longer has an effect",
            )
            self.decision.evacuation_ordered = True  # suppress duplicate proposals
            self.evacuation_timestamp = state.timestamp
            # Signal RiskAgent to stop calling LLM (rules suffice post-evacuation)
            self.risk._evacuation_done = True
            self.audit.log(
                agent="Orchestrator", log_type="STATE_CHANGE", direction="DECISION",
                detail=f"EVACUATION ORDERED at {state.timestamp}",
                source="rule", status="ok",
            )

        # ── Step 4: Evacuation Agent ──────────────────────────────
        # Logistics for an evacuation a human already approved, so this is
        # execution of that decision rather than a new one. The approval it
        # inherits its authority from is recorded on the action.
        evac_action = self.evacuation.process(self.evacuation_ordered, state)
        if evac_action:
            evac_action.metadata.update({
                "source": "human_approved",
                "status": "executed",
                "executed": True,
                "execution_authority": "approved_evacuation_order",
                "authorized_by": self._evacuation_reviewer or "human_supervisor",
            })
            self.bus.publish_action(evac_action)
            self.all_actions.append(evac_action)
            decisions.append(evac_action)
            self.audit.log(
                agent="EvacuationAgent", log_type="EVACUATION", direction="DECISION",
                detail=f"{evac_action.action}: {evac_action.reasoning[:150]}",
                source="human_approved", status="executed",
                data={"action": evac_action.action, "reasoning": evac_action.reasoning,
                      "authorized_by": evac_action.metadata["authorized_by"]},
            )

        # ── Step 5: Comms Agent ───────────────────────────────────
        # Telling Moscow, the IAEA or the public is an outward, irreversible act.
        # It gets the same treatment as any other consequential action: drafted
        # by the agent, inert until a named human signs it.
        comms_proposals = self.comms.process(state, decisions)
        for ca in comms_proposals:
            ca.metadata.update({
                "status": "pending_review",
                "execution_authority": "human_supervisor",
                "executed": False,
                "source": ca.metadata.get("source", "rule"),
            })
        if comms_proposals:
            new_recommendations.extend(
                self._register_recommendations(comms_proposals, agent_input)
            )
            for ca in comms_proposals:
                self.audit.log(
                    agent="CommsAgent", log_type="COMMS_DRAFTED", direction="OUTPUT",
                    detail=f"{ca.action}: drafted for supervisor review",
                    source="rule", status="pending_review",
                )

        # ── Build tick summary ────────────────────────────────────
        counterfactual = AI_COUNTERFACTUAL_DECISIONS.get(state.timestamp)

        audit_entries = self.audit.drain()
        self.store.append_audit(self.run_id, audit_entries)

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
                    "status": d.metadata.get("status", "executed"),
                    "recommendation_id": d.metadata.get("recommendation_id"),
                    "origin_agent": d.metadata.get("origin_agent", d.agent),
                }
                for d in decisions
            ],
            "recommendations": [r.as_dict() for r in new_recommendations],
            "pending_recommendations": self.pending_recommendations(),
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
                "awaiting_human_review": bool(self.pending_recommendations()),
            },
            "llm_stats": self.llm.get_stats(),
            "audit_log": audit_entries,
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
        self.decision = RecommendationAgent(llm_client=self.llm)
        # The safety kernel latches after a trip — it must be re-armed on reset
        # or a replayed run would never trip again.
        self.safety = SafetyKernel()
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
        self.recommendations.clear()
        self._recommendation_by_action.clear()
        self._reviewed_actions.clear()
        self._rejected_at_tick.clear()
        self._rejected_count.clear()
        self._evacuation_reviewer = None
        self.override_history.clear()
        self.total_override_attempts = 0
        self.total_override_failures = 0
        self.total_override_delays = 0
        self.run_id = f"RUN-{uuid4().hex[:10].upper()}"

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
            "pending_recommendations": self.pending_recommendations(),
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
