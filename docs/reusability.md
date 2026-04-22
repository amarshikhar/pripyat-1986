# PRIPYAT-1986 — Reusability & Cross-Industry Transfer

## Overview

PRIPYAT-1986's agent architecture is not specific to nuclear reactors. It implements
a **domain-agnostic safety-critical decision pattern** that transfers to any industry
where: (1) real-time telemetry is monitored, (2) compound failure modes exist,
(3) human override of safety systems is a risk, and (4) rapid response saves lives.

---

## 1. Cross-Industry Agent Mapping

| PRIPYAT-1986 Agent | Oil & Gas | Aviation | Pharmaceuticals | Power Grid |
|--------------------|-----------|----------|-----------------|------------|
| **SensorAgent** (threshold anomaly detection) | SCADA well pressure monitor | Flight parameter envelope checker | Batch process temperature/pH monitor | PMU voltage/frequency monitor |
| **RiskAgent** (rule + LLM blend) | Well blowout probability scorer | Bird strike / turbulence risk scorer | Contamination / cross-reaction risk | N-1 contingency analyser |
| **DecisionAgent** (guardrails + AI) | Emergency well shutdown | Go-around / diversion decision | Batch rejection / line lockdown | Load shedding / islanding decision |
| **EvacuationAgent** (logistics) | Offshore rig evacuation planner | Airport terminal evacuation | Clean room lockdown + personnel routing | Rolling blackout zone planner |
| **CommsAgent** (regulatory notification) | BSEE incident report + coast guard | ATC alert + NTSB notification | FDA deviation report + recall notice | NERC event report + ISO notification |
| **DyatlovAgent** (adversarial pressure) | Production manager override pressure | Captain authority gradient | Manufacturing quota pressure | Grid dispatcher congestion pressure |

---

## 2. The Reusable Pattern: Guardrail-Union Architecture

The core innovation is a **reusable safety pattern** for any domain where AI assists
high-stakes decisions:

```
┌──────────────────────────────────────────────┐
│            Guardrail-Union Pattern            │
│                                              │
│  1. Telemetry → Sensor Agent (deterministic) │
│  2. Alerts → Risk Agent (rule + AI blend)    │
│  3. Risk Score → Decision Agent:             │
│     ├─ Rules run FIRST (safety floor)        │
│     ├─ AI runs SECOND (proactive advisory)   │
│     └─ Final = UNION(rules, AI)              │
│  4. AI can ADD actions, never REMOVE          │
│  5. Hard guardrails are non-negotiable        │
│  6. Graceful degradation to pure rules        │
│                                              │
│  Applicable to ANY safety-critical domain     │
└──────────────────────────────────────────────┘
```

**Why this matters**: Most agentic AI systems let the LLM make final decisions.
In safety-critical domains, this is unacceptable. Our pattern ensures AI enhances
but never weakens the safety floor — making it enterprise-deployable.

---

## 3. Customization Points

To adapt PRIPYAT-1986 for a new industry, only these modules need changes:

| Module | What Changes | What Stays |
|--------|-------------|------------|
| `timeline_data.py` | Replace `ReactorState` with domain dataclass (e.g., `WellState`, `FlightState`) | Data flow pattern |
| `config.py` THRESHOLDS | Replace nuclear thresholds with domain values (e.g., well pressure PSI, altitude ft) | Config structure |
| `llm_client.py` prompts | Replace nuclear expert persona with domain expert | JSON schema pattern, fallback logic |
| `agents.py` SensorAgent | Replace nuclear checks with domain checks | Agent interface, message bus |
| `agents.py` DecisionAgent | Replace action vocabulary (SCRAM → SHUTDOWN, EVACUATE → SHELTER) | Guardrail-union pattern |
| `static/*` dashboard | Replace chart labels and units | Dashboard architecture, WebSocket streaming |

**Everything else is reusable as-is**: orchestrator, message bus, LLM client, simulation engine, dashboard framework, evaluation pipeline.

---

## 4. MCP (Model Context Protocol) Packaging

The agent modules are structured for MCP-compatible packaging:

| MCP Server | Tools Exposed | Description |
|------------|---------------|-------------|
| `sensor-mcp` | `check_thresholds(state)`, `get_alerts()` | Telemetry anomaly detection |
| `risk-mcp` | `assess_risk(state, alerts)`, `get_score_history()` | Risk scoring with AI blend |
| `decision-mcp` | `decide(state, risk_score)`, `get_action_log()` | Guardrailed decision making |
| `evacuation-mcp` | `plan_evacuation(population, routes)`, `get_progress()` | Logistics planning |
| `comms-mcp` | `draft_alert(state, decisions)`, `model_plume(params)` | Communication + dispersion |

Each MCP server exposes typed input/output schemas, making them composable with
any MCP-compatible orchestrator (Azure AI Foundry, Semantic Kernel, AutoGen).

---

## 5. Real-World Validation

The pattern is already validated by real-world deployments:

| Deployment | Organization | PRIPYAT Equivalent |
|------------|-------------|-------------------|
| MISO Azure AI grid platform | Microsoft + MISO (45M people) | Full pipeline: Sensor → Risk → Decision |
| eGridGPT | NREL (US National Lab) | RiskAgent + DecisionAgent |
| ACWA Power predictive maintenance | Microsoft + ACWA Power | SensorAgent + RiskAgent |
| Control Room of the Future | Capgemini (CIGRE 2025) | Complete architecture framework |

---

## 6. Pitch Summary

> *"PRIPYAT-1986 is not a nuclear simulator. It's a reusable safety-critical
> AI architecture that uses Chernobyl as its most dramatic training dataset.
> Connect it to your SCADA API, and it runs on your grid tomorrow.
> Connect it to your BSEE feed, and it monitors your wells.
> The architecture is the product. The disaster is just the proof."*
