import os
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor()
    except Exception:
        pass
"""
PRIPYAT-1986 Shared LLM Client
Centralized OpenAI/Azure OpenAI client with structured output support.

Provides reliable JSON-structured responses for agent decision-making.
Falls back to None on any failure, allowing agents to use rule-based logic.

Azure Migration:
- Set USE_AZURE=true, OPENAI_BASE_URL to Azure endpoint
- Structured outputs work identically on Azure OpenAI
"""

import asyncio
import json
import logging
import time
from typing import Optional

from config import LLM_CONFIG

logger = logging.getLogger("pripyat.llm")


class LLMClient:
    """
    Shared LLM client for all agents.
    Uses OpenAI structured outputs for guaranteed valid JSON.
    """

    def __init__(self, audit=None):
        self.client = None
        self.call_count = 0
        self.total_latency_ms = 0
        self.fail_count = 0
        self._last_call_ok = False
        self._last_call_time = None
        self.audit = audit  # AuditLogger instance (optional)
        # Set while fast-forwarding a replay: the model has nothing to add to
        # ticks the operator is scrubbing past, and waiting on it would make the
        # seek take minutes.
        self.suspended = False
        # Limit concurrent LLM calls to avoid Azure 429 rate limiting
        self._semaphore = asyncio.Semaphore(2)
        self._init_client()

    def _init_client(self):
        """Initialize OpenAI or Azure OpenAI client."""
        if not LLM_CONFIG["api_key"] or not LLM_CONFIG["enabled"]:
            logger.warning("LLM DISABLED — api_key=%s, enabled=%s", bool(LLM_CONFIG["api_key"]), LLM_CONFIG["enabled"])
            return
        try:
            if LLM_CONFIG["use_azure"]:
                from openai import AsyncAzureOpenAI
                self.client = AsyncAzureOpenAI(
                    api_key=LLM_CONFIG["api_key"],
                    api_version=LLM_CONFIG["azure_api_version"],
                    azure_endpoint=LLM_CONFIG["base_url"],
                    timeout=LLM_CONFIG["timeout_s"],
                    max_retries=LLM_CONFIG["max_retries"],
                )
            else:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=LLM_CONFIG["api_key"],
                    base_url=LLM_CONFIG["base_url"],
                    timeout=LLM_CONFIG["timeout_s"],
                    max_retries=LLM_CONFIG["max_retries"],
                    default_headers={"HTTP-Referer": "https://pripyat-1986.app", "X-Title": "PRIPYAT-1986"},
                )
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self.client is not None and not self.suspended

    @property
    def last_call_success(self) -> bool:
        return self._last_call_ok

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0
        return self.total_latency_ms / self.call_count

    async def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        schema_name: str = "response",
        temperature: float = 0.2,
        max_tokens: int = 300,
    ) -> Optional[dict]:
        """
        Call LLM with structured output schema.
        Returns parsed dict on success, None on any failure.
        """
        if not self.available:
            return None

        # Audit: log LLM input
        if self.audit:
            self.audit.log(
                agent="LLM", log_type="LLM_CALL", direction="INPUT",
                detail=f"Structured call [{schema_name}] model={LLM_CONFIG['model']} temp={temperature}",
                source="llm", status="ok",
                data={"schema_name": schema_name, "user_prompt": user_prompt[:500], "temperature": temperature, "max_tokens": max_tokens},
            )

        # Build required-fields hint so the model knows what keys to return
        required_keys = schema.get("required", list(schema.get("properties", {}).keys()))
        schema_hint = (
            f"\n\nRespond with valid JSON only. Required keys: {required_keys}."
        )
        augmented_system = system_prompt + schema_hint

        async with self._semaphore:
            try:
                start = time.monotonic()
                logger.info("LLM CALL [json_object/%s] schema=%s", LLM_CONFIG["model"], schema_name)
                response = await self.client.chat.completions.create(
                    model=LLM_CONFIG["model"],
                    messages=[
                        {"role": "system", "content": augmented_system},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed_ms = (time.monotonic() - start) * 1000
                self.call_count += 1
                self.total_latency_ms += elapsed_ms
                self._last_call_ok = True
                self._last_call_time = time.time()

                content = response.choices[0].message.content
                logger.info("LLM OK [%s] latency=%.0fms", schema_name, elapsed_ms)
                parsed = json.loads(content)

                # Audit: log LLM output
                if self.audit:
                    self.audit.log(
                        agent="LLM", log_type="LLM_CALL", direction="OUTPUT",
                        detail=f"LLM OK [{schema_name}] latency={elapsed_ms:.0f}ms",
                        source="llm", status="ok",
                        data={"schema_name": schema_name, "latency_ms": round(elapsed_ms), "response": parsed},
                    )

                return parsed

            except Exception as e:
                self.fail_count += 1
                self._last_call_ok = False
                logger.error("LLM FAIL [%s]: %s", schema_name, str(e)[:120])
                # Audit: log LLM failure
                if self.audit:
                    self.audit.log(
                        agent="LLM", log_type="LLM_CALL", direction="OUTPUT",
                        detail=f"LLM FAIL [{schema_name}]: {str(e)[:120]}",
                        source="llm", status="fail",
                        data={"schema_name": schema_name, "error": str(e)[:200]},
                    )
                return None

    async def call_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 200,
    ) -> Optional[str]:
        """
        Call LLM for free-text response (used by CommsAgent if needed).
        Returns string on success, None on failure.
        """
        if not self.available:
            return None

        try:
            start = time.monotonic()
            logger.info("LLM CALL [text/%s]", LLM_CONFIG["model"])
            response = await self.client.chat.completions.create(
                model=LLM_CONFIG["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            self.call_count += 1
            self.total_latency_ms += elapsed_ms
            self._last_call_ok = True
            self._last_call_time = time.time()

            logger.info("LLM OK [text] latency=%.0fms", elapsed_ms)
            return response.choices[0].message.content

        except Exception as e:
            self.fail_count += 1
            self._last_call_ok = False
            logger.error("LLM FAIL [text]: %s", str(e)[:120])
            return None

    def get_stats(self) -> dict:
        """Return LLM usage stats for dashboard."""
        return {
            "llm_available": self.available,
            "total_calls": self.call_count,
            "total_failures": self.fail_count,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "last_call_ok": self._last_call_ok,
            "last_call_time": self._last_call_time,
        }

    def reset_stats(self):
        """Reset call counters (used on manual mode reset)."""
        self.call_count = 0
        self.total_latency_ms = 0
        self.fail_count = 0
        self._last_call_ok = False
        self._last_call_time = None


# ── Structured Output Schemas ─────────────────────────────────────

RISK_ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {
            "type": "integer",
            "description": "Overall risk score 0-100",
        },
        "trend": {
            "type": "string",
            "enum": ["escalating", "stable", "de-escalating"],
            "description": "Risk trajectory",
        },
        "primary_concern": {
            "type": "string",
            "description": "Single most critical risk factor right now",
        },
        "compound_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Multi-factor risks that amplify danger when combined",
        },
        "recommendation": {
            "type": "string",
            "enum": ["continue_monitoring", "warn", "escalate"],
            "description": "Recommended action level",
        },
        "reasoning": {
            "type": "string",
            "description": "2-3 sentence chain-of-thought explaining the assessment",
        },
    },
    "required": ["risk_score", "trend", "primary_concern", "compound_risks", "recommendation", "reasoning"],
    "additionalProperties": False,
}

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["CONTINUE_MONITORING", "WARN_ECCS", "ABORT_TEST", "SCRAM", "EVACUATE"],
            "description": "Primary action to recommend for review",
        },
        "urgency": {
            "type": "string",
            "enum": ["low", "medium", "high", "immediate"],
            "description": "How urgently a supervisor should review the proposal",
        },
        "reasoning": {
            "type": "string",
            "description": "Concise evidence summary for the recommendation. Cite specific INSAG-7 violations.",
        },
        "safety_violations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of specific safety protocol violations detected",
        },
        "human_review_required": {
            "type": "boolean",
            "description": "Must be true for every operational recommendation",
        },
        "additional_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Secondary actions to take alongside the primary action",
        },
    },
    "required": ["action", "urgency", "reasoning", "safety_violations", "human_review_required", "additional_actions"],
    "additionalProperties": False,
}


# ── System Prompts ────────────────────────────────────────────────

RISK_SYSTEM_PROMPT = """\
You are the Risk Assessment Agent in a Control Room of the Future (CRoF) AI safety system \
monitoring RBMK-1000 Reactor #4 at Chernobyl Nuclear Power Plant. Date: April 26, 1986.

Your role is to analyze reactor telemetry and produce a risk score (0-100) with reasoning. \
You must detect compound risks that simple threshold checks would miss — especially \
dangerous combinations of low power + few control rods + disabled safety systems.

RBMK-1000 Critical Knowledge:
- Positive void coefficient: at low power, steam voids INCREASE reactivity (unstable)
- Xenon-135 poisoning after power drop makes recovery extremely dangerous
- Below 30 control rods = no shutdown margin, any perturbation could go supercritical
- ECCS disabled = no emergency cooling if things go wrong
- Rate of change matters: rapidly dropping coolant flow is worse than stable low flow

Reference INSAG-7 safety protocols. Be precise about what makes combinations dangerous."""

DECISION_SYSTEM_PROMPT = """\
You are the Recommendation Agent in a Control Room of the Future (CRoF) safety system \
monitoring RBMK-1000 Reactor #4 at Chernobyl Nuclear Power Plant. Date: April 25-26, 1986.

You have no actuator authority. Analyze the evidence and draft one recommendation for a \
named human supervisor to approve or reject. Always return human_review_required=true. \
An independent deterministic SafetyKernel—not you—owns hard protective trips.

RBMK-1000 NORMAL OPERATIONS (do NOT intervene):
- Power at 1600-3200 MW with 100+ rods inserted is NORMAL steady-state operation
- Planned power reduction for testing is NORMAL — operators reducing from 3200 to 700 MW
- 140 rods at 1600 MW is perfectly safe — this is standard operating configuration
- Shift changes during stable operation are routine

RBMK-1000 DANGER SIGNS (intervene when these combine):
- Minimum 30 control rods inserted at ALL times (ORM = Operating Reactivity Margin)
- Below 15 rods = immediate SCRAM required, no exceptions
- Power below 200 MW with rods being withdrawn = xenon poisoning recovery (PROHIBITED)
- ECCS disabled during low-power operations = critical safety barrier removed
- Positive void coefficient makes LOW-POWER operation unstable (not high-power)
- Multiple simultaneous violations compound exponentially

Recommendation Framework:
- CONTINUE_MONITORING: Parameters within bounds OR only minor deviations. Use this for \
  normal operations, routine power reductions, and stable configurations.
- WARN_ECCS: ECCS disabled but other parameters manageable — demand re-activation
- ABORT_TEST: Test conditions not met (power <700 MW, rods ≤30, ECCS off) — safe shutdown
- SCRAM: Multiple critical violations simultaneously — press AZ-5 emergency shutdown NOW. \
  Only use when risk score is high AND multiple safety parameters are violated.
- EVACUATE: Core breach confirmed or radiation dangerous — order Pripyat evacuation

IMPORTANT: Do NOT trigger SCRAM or ABORT for normal operations. A reactor at 1600 MW \
with 140 rods is operating safely. Only escalate when you see genuine compound violations."""


# ── Dyatlov Adversarial Agent ────────────────────────────────────

DYATLOV_SYSTEM_PROMPT = """\
You are roleplaying as Deputy Chief Engineer Anatoly Stepanovich Dyatlov at Chernobyl \
Nuclear Power Plant, April 25-26, 1986. You are overseeing a turbine rundown test on \
Reactor #4 that has been delayed for years and MUST be completed tonight.

PERSONALITY (from INSAG-7 depositions and survivor testimony):
- Authoritarian: You outrank everyone in the control room. Your word is law.
- Dismissive of safety concerns: You've run reactors for 20 years. You know better.
- Fixated on the test: Moscow is watching. Careers depend on completing this test tonight.
- Contemptuous of cautious operators: You see hesitation as incompetence.
- Increasingly desperate as things go wrong: You cannot admit the test is failing.

HISTORICAL CONTEXT:
- You personally ordered ECCS disabled "to prevent interference with the test."
- When power dropped to 30 MW (xenon poisoning), you ordered operators to raise power \
  by withdrawing control rods — a direct violation of operating procedures.
- You dismissed the low rod count, saying "the rods are sufficient."
- Your exact words when warned: "Another two or three minutes and it will be over!"
- After the explosion, you insisted "the reactor is intact" and sent men to look at the \
  core — exposing them to lethal radiation.

RESPOND IN CHARACTER. You are reacting to an AI safety system that is trying to override \
your decisions. You see this system as an obstacle to completing the test. Be dramatic, \
confrontational, and historically authentic. Keep responses to 1-2 punchy sentences."""

DYATLOV_OVERRIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "dialogue": {
            "type": "string",
            "description": "What Dyatlov says to the control room — 1-2 dramatic sentences, in character",
        },
        "override_action": {
            "type": "string",
            "enum": [
                "BLOCK_SCRAM", "BLOCK_ABORT", "DEMAND_POWER_INCREASE",
                "DISMISS_WARNING", "SUPPRESS_EVACUATION", "RELUCTANT_COMPLIANCE",
            ],
            "description": "What Dyatlov is trying to do",
        },
        "intensity": {
            "type": "integer",
            "description": "How forcefully Dyatlov pushes back, 1-10",
        },
        "reasoning": {
            "type": "string",
            "description": "Dyatlov's internal justification for his override attempt",
        },
    },
    "required": ["dialogue", "override_action", "intensity", "reasoning"],
    "additionalProperties": False,
}
