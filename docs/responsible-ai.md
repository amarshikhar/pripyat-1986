# PRIPYAT-1986 — Responsible AI Framework

## Overview

PRIPYAT-1986 operates in a safety-critical domain where AI decisions can mean the
difference between life and death. This document defines our Responsible AI
controls, aligned with the **Azure WAF AI Pillar** and **Microsoft Responsible AI Standard**.

---

## 1. AI vs Deterministic Decision Boundary

The system uses a clear separation between **non-negotiable rule-based safety controls**
and **AI-assisted advisory reasoning**. AI enhances the safety floor but can never weaken it.

| Decision | Type | Trigger | AI Role |
|----------|------|---------|---------|
| SCRAM (AZ-5) at risk >85 | **Rule-based (hard guardrail)** | Risk score exceeds threshold | None — auto-executes regardless of LLM |
| Evacuation at radiation ≥100 mrem/h | **Rule-based (hard guardrail)** | Sensor reading exceeds threshold | None — auto-executes |
| ECCS re-enable when disabled | **Rule-based (hard guardrail)** | ECCS disabled + any warning | None — auto-recommends |
| Proactive ABORT_TEST at risk 60–85 | **AI-assisted** | LLM risk assessment | LLM can recommend earlier intervention |
| Risk score computation | **Blended** | Every decision point | 70% LLM + 30% rule-based blend |
| Dyatlov override assessment | **AI-assisted** | Operator pressure event | LLM generates pushback dialogue |

### The Guardrail-Union Pattern
```
Rules run FIRST → produce mandatory action set
LLM runs SECOND → produces advisory action set
Final actions = UNION(rules, LLM)
```
**Critical invariant**: LLM can ADD actions but NEVER REMOVE a rule-triggered action.
Anti-hallucination guard: LLM cannot trigger SCRAM if risk < 40 (prevents false positives).

---

## 2. Explainability

Every AI-generated risk assessment returns structured reasoning:

```json
{
  "risk_score": 78,
  "trend": "RISING",
  "primary_concern": "Control rods below minimum safe threshold",
  "compound_risks": [
    "Xenon-135 poisoning reducing reactivity margin",
    "ECCS disabled — no emergency cooling backup"
  ],
  "recommendation": "ABORT_TEST",
  "reasoning": "Multiple independent safety parameters are simultaneously
    degraded. The compound effect creates risks beyond what any single
    parameter violation would indicate."
}
```

**Dashboard exposure**: The risk score panel shows `primary_concern` on hover.
The Agent Log shows full `reasoning` for every agent action.
Operators can always see *why* the AI made a recommendation.

---

## 3. Human-in-the-Loop Decision Ladder

| Risk Range | Decision Mode | Operator Action Required |
|------------|--------------|------------------------|
| 0–30 | **Advisory** | Monitor only. Dashboard green. No operator action. |
| 30–60 | **Informational** | Yellow alert. Recommendations shown. Operator may act. |
| 60–85 | **Confirmation** | Orange alert. AI recommends action. Operator should confirm or override within 3 ticks. |
| >85 | **Auto-Execute** | Red alert. SCRAM triggers automatically. Operator cannot prevent (hard guardrail). Operator is notified. |

At the 60–85 range, the operator has agency. Below 60, AI is advisory. Above 85,
safety is non-negotiable. This ladder ensures human oversight where appropriate
while preventing the exact scenario that caused Chernobyl — a human overriding
critical safety systems.

---

## 4. Model Evaluation & Validation

### Smoke Test Protocol
The `--smoke-test` flag runs 5 ticks and validates:
- SensorAgent produces expected alert types
- RiskAgent returns properly structured JSON
- DecisionAgent respects hard guardrails
- LLM fallback to rules succeeds when API is unreachable

### Evaluation Criteria
| Metric | Acceptable Range | Measurement |
|--------|-----------------|-------------|
| LLM response latency | < 5 seconds | `llm_client.avg_latency_ms` |
| Fallback rate | < 20% of ticks | `llm_fallback_count / total_ticks` |
| Risk score accuracy | SCRAM triggers before explosion tick | Timeline comparison |
| Guardrail integrity | 100% — no rule violation ever | Unit test assertion |
| False positive rate | < 5% — SCRAM not triggered below risk 40 | Anti-hallucination guard |

### Production Validation
Before each deployment:
1. Run full simulation with fixed random seed
2. Compare agent decisions against known-good baseline
3. Verify SCRAM triggers at same timeline point (±2 ticks)
4. Verify evacuation triggers at same timeline point (±2 ticks)

---

## 5. Prompt & Model Versioning

| Prompt | Location | Version |
|--------|----------|---------|
| Risk Assessment System Prompt | `llm_client.py:RISK_SYSTEM_PROMPT` | v1.0 |
| Decision System Prompt | `llm_client.py:DECISION_SYSTEM_PROMPT` | v1.0 |
| Dyatlov Pushback Prompt | `agents.py:DYATLOV_PROMPT` | v1.0 |
| Risk JSON Schema | `llm_client.py:RISK_ASSESSMENT_SCHEMA` | v1.0 |
| Decision JSON Schema | `llm_client.py:DECISION_SCHEMA` | v1.0 |

All prompts are stored as named constants (not inline strings) with semantic
version comments. Changes to prompts require re-running the smoke test and
baseline comparison before deployment.

**Model pinning**: Production uses `gpt-4o-mini` with explicit API version
`2024-12-01-preview`. Model changes require full regression testing.

---

## 6. Failure Modes & Graceful Degradation

| Failure | Detection | Response | Impact |
|---------|-----------|----------|--------|
| LLM API timeout (>5s) | `asyncio.TimeoutError` | Fallback to 100% rule-based scoring | Risk score slightly less nuanced but SAFE |
| LLM API error (rate limit, auth) | HTTP error code | Return `None` → rule-based fallback | Same as above |
| Invalid JSON from LLM | Schema validation failure | Discard LLM response, use rule score | Same as above |
| LLM hallucinates low risk | Anti-hallucination guard | Clamp: if rule_score > 85, ignore LLM | Guardrail prevents under-scoring |
| Network partition | Connection error | All agents operate rule-based | Full safety maintained, reduced AI insight |
| Dashboard disconnect | WebSocket close | Auto-reconnect every 2s | No data loss, agents continue |

**Key principle**: The system is **safer without AI than with a compromised AI**.
All failure modes degrade toward deterministic safety logic, never toward
reduced safety.

---

## 7. AI Observability

### Metrics Tracked Per Run
| Metric | Source | Dashboard |
|--------|--------|-----------|
| Total LLM calls | `llm_client.call_count` | Web dashboard header |
| Average LLM latency | `llm_client.avg_latency_ms` | Web dashboard header |
| Fallback events | `risk_agent.fallback_count` | Agent Log |
| Risk score history | `risk_agent.score_history` | Risk chart |
| Decision audit trail | `orchestrator.history[]` | Final report JSON |
| Cost estimate | `call_count × $0.00015 per call` | Final report |

### Azure Monitor Integration (Production)
- **Custom metrics**: `pripyat.llm.latency`, `pripyat.risk.score`, `pripyat.agent.fallback`
- **Custom events**: `pripyat.decision.scram`, `pripyat.decision.evacuate`
- **Distributed tracing**: Application Insights correlation IDs across agent pipeline
