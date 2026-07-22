# PRIPYAT-1986 — Responsible AI Framework

## Overview

PRIPYAT-1986 is an educational counterfactual in a safety-critical domain. AI
never receives actuator authority. This document defines our Responsible AI
controls, aligned with the **Azure WAF AI Pillar** and **Microsoft Responsible AI Standard**.

---

## 1. AI vs Deterministic Decision Boundary

The system separates three authorities: an advisory AI lane, an attributable
human-review lane, and an independent deterministic safety-instrumented lane.

| Decision | Type | Trigger | AI Role |
|----------|------|---------|---------|
| SCRAM (AZ-5) | **SafetyKernel protective trip** | Raw critical rods/coolant/pressure/temperature telemetry | None; the kernel accepts no AI score |
| Evacuation | **Human-reviewed operational action** | Pending rule/AI proposal | Explain and recommend only |
| ECCS re-enable | **Human-reviewed operational action** | Pending rule/AI proposal | Explain and recommend only |
| Proactive ABORT_TEST at risk 60–85 | **AI-assisted** | LLM risk assessment | LLM can recommend earlier intervention |
| Risk score computation | **Blended** | Every decision point | 70% LLM + 30% rule-based blend |
| Dyatlov override assessment | **AI-assisted** | Operator pressure event | LLM generates pushback dialogue |

### The Authority-Separation Pattern
```
Raw telemetry → SafetyKernel → executed protective trip (no override path)
Telemetry/context → AI/rules → pending recommendation → human approve/reject
```
**Critical invariants**: an AI response never sets plant state; a rejected review
is final; an approved proposal is executed once; the SafetyKernel never consumes
an LLM-derived risk score.

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

**Dashboard exposure**: Triage / Cases preserves the exact reactor telemetry,
component risk scores, sensor alerts, historical context, recommendation
reasoning, authority boundary, and signed reviewer outcome. Operators can
inspect *why* a recommendation was created before deciding it.

---

## 3. Human-in-the-Loop Decision Ladder

| Risk Range | Decision Mode | Operator Action Required |
|------------|--------------|------------------------|
| 0–30 | **Advisory** | Monitor only. Dashboard green. No operator action. |
| 30–60 | **Informational** | Yellow alert. Recommendations remain inert. |
| 60–100 | **Human review** | Replay pauses; a named supervisor approves or rejects the proposal. |
| Any raw hard-trip condition | **SafetyKernel trip** | Deterministic SCRAM executes independently of AI and human review. |

The human retains authority over operational decisions, while the simulated
protective system retains authority over its narrow hard-trip envelope. This is
the distinction missing from the earlier implementation, where a blended AI
risk score could directly change reactor state.

---

## 4. Model Evaluation & Validation

### Smoke Test Protocol
The `--smoke-test` flag runs 5 ticks and validates:
- SensorAgent produces expected alert types
- RiskAgent returns properly structured JSON
- RecommendationAgent output remains pending until human review
- SafetyKernel trips from raw critical telemetry and cannot be overridden
- LLM fallback to rules succeeds when API is unreachable

### Evaluation Criteria
| Metric | Acceptable Range | Measurement |
|--------|-----------------|-------------|
| LLM response latency | < 5 seconds | `llm_client.avg_latency_ms` |
| Fallback rate | < 20% of ticks | `llm_fallback_count / total_ticks` |
| Authority integrity | 100% — no agent proposal directly executes | Unit test assertion |
| Safety-kernel isolation | 100% — no LLM score is an input | API and unit-test assertion |
| Protective-trip recall | 100% on frozen critical fixtures | Evaluation confusion matrix |
| False protective-trip rate | 0% on frozen non-trip fixtures | Evaluation confusion matrix |
| Human-review recall | 100% on frozen major-decision fixtures | Evaluation confusion matrix |

The Evaluations workspace reports the full three-class confusion matrix for
`monitor`, `human_review`, and `protective_trip`, plus each scenario’s raw
telemetry, activated rules, recommendations, and authority route. Model calls
are disabled so this suite is reproducible and tests the control boundary—not
the quality of a particular model response.

> This frozen fixture set is a software regression benchmark, not a nuclear
> safety certification or evidence that the simplified physics model is valid
> for operational use.

### Production Validation
Before each deployment:
1. Run full simulation with fixed random seed
2. Verify agent recommendations remain inert before approval
3. Verify deterministic trips trigger from each raw critical condition
4. Verify approve/reject finality and idempotency
5. Run the confusion-matrix evaluation and investigate every off-diagonal result

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
| LLM hallucinates risk/action | Schema and authority boundary | Store as inert proposal or discard | No direct plant effect |
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
| Decision audit trail | SQLite `audit_events` | Persistent Audit workspace |
| Detailed review cases | SQLite `cases` | Triage / Cases workspace |
| Cost estimate | `call_count × $0.00015 per call` | Final report |

### Azure Monitor Integration (Production)
- **Custom metrics**: `pripyat.llm.latency`, `pripyat.risk.score`, `pripyat.agent.fallback`
- **Custom events**: `pripyat.decision.scram`, `pripyat.decision.evacuate`
- **Distributed tracing**: Application Insights correlation IDs across agent pipeline
